"""Generate an isolated, named application using the existing build pipeline."""

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


EXCLUDED_DIRS = {
    '.git', '.agents', '.codex', '.aws', '__pycache__', 'target', 'build',
    '.dart_tool', '.gradle', '.plugin_symlinks', 'ephemeral', 'Pods',
    'node_modules', 'vcpkg_installed', 'third_party', '.flatpak-builder',
    'AppDir', 'appimage-build', 'graphify-out',
}
PACKAGING_FILES = {
    'build.py', 'res/PKGBUILD', 'res/pacman_install', 'res/osx-dist.sh',
    'res/rustdesk.desktop', 'res/rustdesk-link.desktop', 'res/rustdesk.service',
}
# These names belong to dependencies, native interfaces or upstream services.
PROTECTED = re.compile(
    r'https?://[^\s\"\'<>]+|'
    r'(?:[\w.+-]+@)?(?:[\w-]+\.)*rustdesk\.(?:com|org)\b|'
    r'librustdesk|rustdesk-portable-packer|org\.rustdesk\.rustdesk|'
    r'RustDeskPrinterDriver|RustDeskIddDriver|RustDeskTempTopMostWindow|'
    r'RuntimeBroker_rustdesk'
)
NAME_TOKEN = re.compile(r'(?<![A-Za-z0-9_])(RustDesk|rustdesk)(?![A-Za-z0-9_])')


def validate_brand_name(value):
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9-]{0,49}', value):
        raise argparse.ArgumentTypeError(
            'Brand name must start with an ASCII letter and contain at most 50 '
            'letters, digits or hyphens; spaces and shell characters are unsupported.')
    reserved = {'CON', 'PRN', 'AUX', 'NUL'}
    reserved.update('COM' + str(i) for i in range(1, 10))
    reserved.update('LPT' + str(i) for i in range(1, 10))
    if value.upper() in reserved:
        raise argparse.ArgumentTypeError('Brand name is a reserved Windows device name.')
    return value


def package_text(text, name):
    parts = PROTECTED.split(text)
    protected = PROTECTED.findall(text)
    for i, part in enumerate(parts):
        parts[i] = NAME_TOKEN.sub(
            lambda match: name if match[0] == 'RustDesk' else name.lower(), part)
    return ''.join(part + (protected[i] if i < len(protected) else '')
                   for i, part in enumerate(parts))


def brand_text(relative, text, name):
    slug = name.lower()
    bundle_id = 'com.carriez.' + slug
    gtk_id = 'com.carriez.' + slug.replace('-', '_')
    if relative == 'Cargo.toml':
        # Keep the Cargo package/library names and lockfile; name the main binary explicitly.
        text = text.replace('default-run = "rustdesk"', 'default-run = "' + slug + '"')
        text = text.replace('[[bin]]', '[[bin]]\nname = "' + slug +
                            '"\npath = "src/main.rs"\n\n[[bin]]', 1)
        text = text.replace('"RustDesk', '"' + name)
        text = text.replace('"rustdesk.exe"', '"' + slug + '.exe"')
        return text.replace('com.carriez.rustdesk', bundle_id)
    if relative == 'libs/portable/Cargo.toml':
        return package_text(text, name)
    if relative == 'res/msi/preprocess.py':
        # Its canonical RustDesk checks select the per-brand MSI UpgradeCode.
        return text.replace('default="RustDesk"', 'default="' + name + '"')
    if relative == 'src/lang.rs' or relative.startswith('src/lang/'):
        return text
    packaging = (relative in PACKAGING_FILES or relative.startswith('res/DEBIAN/')
                 or (relative.startswith('res/rpm') and relative.endswith('.spec'))
                 or relative.startswith(('appimage/', 'flatpak/')))
    if packaging:
        text = package_text(text, name)
        if relative == 'build.py':
            # A source snapshot has no Git checkout to reset on Arch Linux.
            text = text.replace("if os.path.isfile('/usr/bin/pacman'):\n"
                                "        system2('git checkout src/ui/common.tis')",
                                "if os.path.isfile('/usr/bin/pacman') and os.path.isdir('.git'):\n"
                                "        system2('git checkout src/ui/common.tis')")
        return text
    if relative.startswith(('flutter/windows/', 'flutter/linux/', 'flutter/macos/',
                            'flutter/ios/', 'flutter/android/app/src/main/res/',
                            'src/platform/privileges_scripts/')) or relative == 'flutter/android/app/src/main/AndroidManifest.xml':
        text = package_text(text, name)
        text = text.replace('com.carriez.flutterHbb', bundle_id)
        if relative == 'flutter/linux/CMakeLists.txt':
            text = text.replace('com.carriez.flutter_hbb', gtk_id)
        if relative == 'flutter/linux/my_application.cc':
            text = text.replace('set_title(header_bar, "' + slug + '")',
                                'set_title(header_bar, "' + name + '")')
            text = text.replace('set_title(window, "' + slug + '")',
                                'set_title(window, "' + name + '")')
        if relative.startswith('src/platform/privileges_scripts/'):
            text = text.replace('RustDesk_', name + '_')
        # Xcode converts hyphens in PRODUCT_MODULE_NAME to underscores.
        if relative.endswith('.xib'):
            text = text.replace('customModule="' + name + '"',
                                'customModule="' + name.replace('-', '_') + '"')
        return text
    if relative == 'flutter/android/app/build.gradle':
        # The Java namespace is also used by JNI; applicationId is the installed identity.
        return text.replace('applicationId "com.carriez.flutter_hbb"',
                            'applicationId "' + gtk_id + '"')
    if relative.startswith('flutter/android/app/src/main/kotlin/'):
        return text.replace('"RustDesk', '"' + name).replace(
            '"rustdesk:wakelock"', '"' + slug + ':wakelock"')
    if relative == 'libs/hbb_common/src/config.rs':
        return text.replace('RwLock::new("RustDesk".to_owned())',
                            'RwLock::new("' + name + '".to_owned())')
    if relative == 'libs/portable/src/main.rs':
        return text.replace('const APP_PREFIX: &str = "rustdesk";',
                            'const APP_PREFIX: &str = "' + slug + '";')
    if relative.startswith(('src/', 'flutter/lib/', 'libs/scrap/')):
        # Translation keys, wire formats, driver names and FFI symbols stay canonical.
        for prefix in ('/usr/share/', '/usr/lib/', '/usr/bin/', '/app/share/', '/app/bin/'):
            text = text.replace(prefix + 'rustdesk', prefix + slug)
        text = text.replace('rustdesk://', slug + '://')
        if relative in ('src/platform/macos.rs', 'src/updater.rs'):
            for token in ('.rustdeskupdate', '.rustdeskdownload', '.rustdeskmount',
                          'rustdesk_update.sh', 'rustdesk_root_update.log',
                          '/var/run/rustdesk-update.lock'):
                text = text.replace(token, token.replace('rustdesk', slug))
        if relative == 'src/platform/macos.rs':
            text = text.replace('com.carriez.rustdesk', bundle_id)
        if relative == 'src/platform/windows.rs':
            text = text.replace('"RustDesk"', '"' + name + '"')
            text = text.replace('"RustDesk Output"', '"' + name + ' Output"')
            text = text.replace('"RustDeskCustomClientStaging"', '"' + name + 'CustomClientStaging"')
            text = text.replace('"rustdesk.exe"', '"' + slug + '.exe"')
        if relative.startswith('src/whiteboard/') or relative == 'src/auth_2fa.rs':
            text = text.replace('"RustDesk', '"' + name)
        if relative == 'src/server/dbus.rs':
            text = text.replace('org.rustdesk.rustdesk', 'org.' + slug.replace('-', '_') + '.app')
        if relative == 'flutter/lib/desktop/widgets/tabbar_widget.dart':
            text = text.replace('"RustDesk"', '"' + name + '"')
    return text


def prepare_brand(repo_root, name, output_root=None):
    validate_brand_name(name)
    root = Path(repo_root).resolve()
    parent = Path(output_root) if output_root is not None else root / 'build' / 'brands'
    destination = parent.resolve() / name.lower()
    destination.mkdir(parents=True, exist_ok=True)
    manifest_path = destination / '.brand.json'
    previous = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    managed = []
    changed = []
    for directory, directories, files in os.walk(str(root)):
        directories[:] = [entry for entry in directories if entry not in EXCLUDED_DIRS
                          and not (Path(directory) / entry).is_symlink()
                          and (Path(directory) / entry).resolve() != destination.parent]
        for filename in files:
            source = Path(directory) / filename
            relative = source.relative_to(root).as_posix()
            if filename in {'.DS_Store', '.brand.json'} or source.is_symlink():
                continue
            if source.suffix in {'.deb', '.rpm', '.dmg', '.AppImage', '.pyc'}:
                continue
            if filename.startswith(('librustdesk.', 'liblibrustdesk.')):
                continue
            target_relative = relative
            if relative in PACKAGING_FILES and relative.startswith('res/rustdesk'):
                target_relative = relative.replace('rustdesk', name.lower())
            if relative.startswith('flatpak/'):
                target_relative = package_text(relative, name)
            target = destination / target_relative
            target.parent.mkdir(parents=True, exist_ok=True)
            original = source.read_bytes()
            updated = original
            if relative not in {'res/branding.py', 'res/test_branding.py'}:
                try:
                    updated = brand_text(relative, original.decode('utf-8'), name).encode('utf-8')
                except UnicodeDecodeError:
                    pass
            if not target.exists() or target.read_bytes() != updated:
                target.write_bytes(updated)
                if updated == original:
                    shutil.copystat(str(source), str(target))
                else:
                    shutil.copymode(str(source), str(target))
            managed.append(target_relative)
            if updated != original or target_relative != relative:
                changed.append(target_relative)
    for obsolete in set(previous.get('managed_files', [])) - set(managed):
        if Path(obsolete).is_absolute() or '..' in Path(obsolete).parts:
            raise ValueError('Invalid managed path in ' + str(manifest_path))
        old_file = destination / obsolete
        if old_file.is_file():
            old_file.unlink()
    manifest_path.write_text(json.dumps({
        'name': name, 'binary_name': name.lower(),
        'managed_files': sorted(managed), 'changed_files': sorted(changed),
    }, indent=2) + '\n', encoding='utf-8')
    return destination


def forwarded_arguments(arguments):
    forwarded = []
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        option = argument.split('=', 1)[0]
        if option.startswith('--') and '--brand-name'.startswith(option):
            index += 1 if '=' in argument else 2
            continue
        if option.startswith('--') and '--prepare-brand-only'.startswith(option):
            index += 1
            continue
        forwarded.append(argument)
        index += 1
    return forwarded


def build_brand(repo_root, args, arguments):
    destination = prepare_brand(repo_root, args.brand_name)
    print('Brand: {}\nBuild directory: {}'.format(args.brand_name, destination), flush=True)
    if args.prepare_brand_only:
        return 0
    environment = os.environ.copy()
    environment['CARGO_TARGET_DIR'] = str(destination / 'target')
    if args.flutter and sys.platform == 'darwin':
        if not environment.get('VCPKG_ROOT'):
            vcpkg_root = Path.home() / 'development' / 'vcpkg'
            if (vcpkg_root / 'installed').is_dir():
                environment['VCPKG_ROOT'] = str(vcpkg_root)
        path = environment.get('PATH', os.defpath)
        if not shutil.which('flutter', path=path):
            # Existing terminals may predate the SDK's shell PATH entry.
            flutter_bin = Path.home() / 'development' / 'flutter' / 'bin'
            if shutil.which('flutter', path=str(flutter_bin)):
                environment['PATH'] = str(flutter_bin) + os.pathsep + path
    try:
        if args.flutter:
            result = subprocess.run(['flutter', 'pub', 'get'],
                                    cwd=str(destination / 'flutter'), env=environment)
            if result.returncode:
                return result.returncode
        return subprocess.run([sys.executable, str(destination / 'build.py')] +
                              forwarded_arguments(arguments), cwd=str(destination),
                              env=environment).returncode
    except FileNotFoundError as error:
        print('Build tool unavailable: {}'.format(error), file=sys.stderr)
        return 1
