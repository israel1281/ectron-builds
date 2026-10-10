"""Submit source snapshots to native GitHub runners without a local Git checkout."""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import uuid

from res.branding import EXCLUDED_DIRS


WORKFLOW = 'branded-desktop.yml'
FORMATS = {'macos': ('dmg',), 'windows': ('exe', 'msi'), 'linux': ('deb',)}


def add_arguments(parser):
    parser.add_argument('--platform', choices=('mac', 'macos', 'windows', 'linux'),
                        help='Build on a native GitHub Actions runner, from any host.')
    parser.add_argument('--package-format', choices=('dmg', 'exe', 'msi', 'deb'),
                        help='Package type; defaults to dmg, exe or deb for the selected platform.')
    parser.add_argument('--github-repo', metavar='OWNER/REPO',
                        help='Dedicated GitHub build repository; saved after a successful upload.')
    parser.add_argument('--no-wait', action='store_true',
                        help='Submit the build and return its URL without downloading the result.')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show build settings without uploading or compiling.')


def copy_snapshot(root, destination):
    # Include checked-out submodule contents, but never credentials or generated artifacts.
    excluded = EXCLUDED_DIRS | {'.ssh', '.vscode', '.idea'}
    for directory, directories, files in os.walk(str(root)):
        directories[:] = [name for name in directories if name not in excluded
                          and not (Path(directory) / name).is_symlink()]
        for name in files:
            source = Path(directory) / name
            if source.is_symlink() or name in {'.git', '.gitmodules', '.DS_Store', '.brand.json'}:
                continue
            if name.startswith('.env') or source.suffix.lower() in {
                    '.pfx', '.p12', '.pem', '.key', '.pyc', '.dmg', '.exe', '.deb', '.rpm',
                    '.appimage', '.so', '.dylib', '.dll', '.zip', '.tgz'}:
                continue
            relative = source.relative_to(root)
            # Upstream automation publishes releases and schedules unrelated builds.
            if relative.parts[:2] == ('.github', 'workflows') and name != WORKFLOW:
                continue
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(source), str(target))


def command(arguments, cwd=None, capture=False):
    result = subprocess.run(arguments, cwd=str(cwd) if cwd else None, check=True,
                            stdout=subprocess.PIPE if capture else None, text=True)
    return result.stdout.strip() if capture else None


def build_platform(root, args, parser):
    root = Path(root)
    target = 'macos' if args.platform == 'mac' else args.platform
    package = args.package_format or FORMATS[target][0]
    if package not in FORMATS[target]:
        parser.error('{} packages require --platform {}'.format(package, next(
            platform for platform, formats in FORMATS.items() if package in formats)))
    if (args.prepare_brand_only or args.skip_cargo or args.package or args.portable
            or args.vram or args.drm or args.feature or getattr(args, 'screencapturekit', False)):
        parser.error('Platform builds support --brand-name, --hwcodec and --unix-file-copy-paste; '
                     'use the native build command for other build options.')
    if args.unix_file_copy_paste and target == 'windows':
        parser.error('--unix-file-copy-paste is only supported for macOS/Linux')
    config = root / 'build/github.json'
    repository = args.github_repo or os.environ.get('RUSTDESK_BUILD_REPO')
    if not repository and config.exists():
        repository = json.loads(config.read_text())['repository']
    if repository and not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*', repository):
        parser.error('--github-repo must be OWNER/REPO')
    brand = args.brand_name or 'RustDesk'
    settings = {'repository': repository, 'platform': target, 'package_format': package,
                'brand_name': brand, 'hwcodec': args.hwcodec,
                'unix_file_copy_paste': args.unix_file_copy_paste}
    print(json.dumps(settings, indent=2), flush=True)
    if args.dry_run:
        return 0
    if not repository:
        parser.error('Set --github-repo OWNER/REPO to a dedicated build repository first.')
    try:
        command(['gh', 'auth', 'status', '--hostname', 'github.com'], capture=True)
        metadata = json.loads(command(['gh', 'repo', 'view', repository, '--json',
                                       'defaultBranchRef'], capture=True))
        default_branch = (metadata.get('defaultBranchRef') or {}).get('name')
        if default_branch:
            # Dispatch requires this workflow on the default branch. Never replace another repo.
            command(['gh', 'api', 'repos/{}/contents/.github/workflows/{}'.format(
                repository, WORKFLOW), '--method', 'GET', '-f', 'ref=' + default_branch], capture=True)
        branch = 'codex/build-' + uuid.uuid4().hex[:12] if default_branch else 'main'
        with tempfile.TemporaryDirectory(prefix='ectron-source-') as temporary:
            snapshot = Path(temporary)
            copy_snapshot(root, snapshot)
            command(['git', 'init', '-b', branch], snapshot, capture=True)
            command(['git', 'add', '--force', '.'], snapshot)
            command(['git', '-c', 'user.name=Desktop Builder', '-c',
                     'user.email=builder@users.noreply.github.com', 'commit', '-m',
                     'Source snapshot for {} {} {}'.format(brand, target, package)], snapshot, True)
            command(['git', '-c', 'credential.helper=', '-c',
                     'credential.helper=!gh auth git-credential', 'push',
                     'https://github.com/' + repository + '.git', 'HEAD:refs/heads/' + branch], snapshot)
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text(json.dumps({'repository': repository}, indent=2) + '\n')
        dispatch = ['gh', 'workflow', 'run', WORKFLOW, '--repo', repository, '--ref', branch]
        for key, value in settings.items():
            if key != 'repository':
                dispatch.extend(['-f', key + '=' + (str(value).lower() if isinstance(value, bool) else value)])
        # GitHub may take a few seconds to register a newly uploaded workflow.
        for attempt in range(12):
            try:
                command(dispatch)
                break
            except subprocess.CalledProcessError:
                if attempt == 11:
                    raise
                time.sleep(5)
        run = None
        for attempt in range(24):
            runs = json.loads(command(['gh', 'run', 'list', '--repo', repository,
                                      '--workflow', WORKFLOW, '--branch', branch,
                                      '--event', 'workflow_dispatch', '--json', 'databaseId,url',
                                      '--limit', '1'], capture=True))
            if runs:
                run = runs[0]
                break
            time.sleep(5)
        if not run:
            raise RuntimeError('Build submitted; locate it at https://github.com/' + repository + '/actions')
        print('Build: ' + run['url'], flush=True)
        if args.no_wait:
            return 0
        run_id = str(run['databaseId'])
        command(['gh', 'run', 'watch', run_id, '--repo', repository, '--exit-status', '--interval', '30'])
        output = root / 'build/artifacts' / brand.lower() / target / run_id
        output.mkdir(parents=True, exist_ok=True)
        command(['gh', 'run', 'download', run_id, '--repo', repository, '--name',
                 'desktop-{}-{}'.format(target, package), '--dir', str(output)])
        print('Downloaded package: ' + str(output), flush=True)
        return 0
    except FileNotFoundError as error:
        print('Missing build tool: {}. Install Git and GitHub CLI, then run gh auth login.'.format(error))
    except (subprocess.CalledProcessError, RuntimeError) as error:
        print('Platform build failed: {}'.format(error))
    return 1
