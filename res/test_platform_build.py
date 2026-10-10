import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from res.ci_build import run
from res.platform_build import copy_snapshot


ROOT = Path(__file__).resolve().parents[1]


class PlatformBuildTests(unittest.TestCase):
    def test_flutter_launcher_uses_resolved_windows_batch_path(self):
        with patch('res.ci_build.shutil.which', return_value='C:/flutter/bin/flutter.bat'), \
                patch('res.ci_build.subprocess.run') as execute:
            run(['flutter', 'pub', 'get'], Path('client'), {'PATH': 'sdk'})
            execute.assert_called_once_with(['C:/flutter/bin/flutter.bat', 'pub', 'get'],
                                            cwd='client', env={'PATH': 'sdk'}, check=True)

    def test_source_snapshot_preserves_assets_and_submodules(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / 'source'
            output = Path(temporary) / 'snapshot'
            included = ['libs/hbb_common/src/lib.rs', 'res/icon.png', 'res/icon.ico',
                        '.github/workflows/branded-desktop.yml', '.github/patches/sdk.diff']
            excluded = ['.git/config', 'libs/hbb_common/.git', 'build/brands/ectron/Cargo.toml',
                        '.env', '.env.local', 'cert.pfx', '.aws/credentials',
                        'flutter/build/app', 'graphify-out/graph.json',
                        '.github/workflows/nightly.yml']
            for relative in included + excluded:
                path = source / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('fixture')
            copy_snapshot(source, output)
            self.assertEqual(sorted(p.relative_to(output).as_posix() for p in output.rglob('*')
                                    if p.is_file()), sorted(included))
            self.assertEqual((source / '.git/config').read_text(), 'fixture')

    def test_platform_cli_selects_and_validates_packages(self):
        for platform, package in [('mac', 'dmg'), ('windows', 'msi'), ('windows', 'exe'), ('linux', 'deb')]:
            result = subprocess.run([sys.executable, str(ROOT / 'build.py'), '--platform', platform,
                                     '--package-format', package, '--brand-name', 'ectron', '--dry-run'],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['package_format'], package)
        for arguments in [['--platform', 'linux', '--package-format', 'msi', '--dry-run'],
                          ['--package-format', 'exe'], ['--platform', 'windows', '--skip-cargo'],
                          ['--platform', 'linux', '--github-repo', '../bad', '--dry-run']]:
            result = subprocess.run([sys.executable, str(ROOT / 'build.py')] + arguments,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)


if __name__ == '__main__':
    unittest.main()
