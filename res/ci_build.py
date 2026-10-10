"""Build and package a branded desktop client on its native runner."""

import argparse
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile

from res.branding import prepare_brand, validate_brand_name
from res.connection_role import add_arguments, package_suffix, prepare_role
from res.platform_build import FORMATS


def run(arguments, directory, environment):
    executable = shutil.which(arguments[0], path=environment.get('PATH')) or arguments[0]
    subprocess.run([executable] + arguments[1:], cwd=str(directory), env=environment, check=True)


def finalize_macos_app(app, directory, environment):
    # The legacy build adds service after Xcode signs the app, invalidating its resource seal.
    run(['codesign', '--force', '--sign', '-', '--timestamp=none',
         str(app / 'Contents/MacOS/service')], directory, environment)
    # Ad hoc builds have no Team ID for hardened runtime's library validation.
    run(['codesign', '--force', '--sign', '-', '--timestamp=none',
         '--options=0', '--preserve-metadata=entitlements', str(app)], directory, environment)
    run(['codesign', '--verify', '--deep', '--strict', '--verbose=2', str(app)],
        directory, environment)


def build(root, args):
    host = {'Darwin': 'macos', 'Windows': 'windows', 'Linux': 'linux'}.get(platform.system())
    if host != args.platform or args.package_format not in FORMATS[host]:
        raise ValueError('Run {} {} builds on a native {} host.'.format(
            args.platform, args.package_format, args.platform))
    stage = prepare_brand(root, args.brand_name)
    environment = os.environ.copy()
    prepare_role(stage, args, environment)
    environment['CARGO_TARGET_DIR'] = str(stage / 'target')
    if host == 'linux':
        script = stage / 'build.py'
        script.write_text(script.read_text().replace(
            'dpkg-deb -b tmpdeb', 'dpkg-deb --root-owner-group -b tmpdeb'))
    if host == 'macos' and platform.machine().lower() in ('arm64', 'aarch64'):
        replacements = {
            'build.py': (r'MACOSX_DEPLOYMENT_TARGET=10\.14', 'MACOSX_DEPLOYMENT_TARGET=12.3'),
            'flutter/macos/Podfile': (r"platform :osx, '[^']+'", "platform :osx, '12.3'"),
            'Cargo.toml': (r'osx_minimum_system_version = "[^"]+"', 'osx_minimum_system_version = "12.3"'),
            'flutter/macos/Runner.xcodeproj/project.pbxproj':
                (r'MACOSX_DEPLOYMENT_TARGET = [0-9.]+;', 'MACOSX_DEPLOYMENT_TARGET = 12.3;'),
        }
        for relative, (pattern, replacement) in replacements.items():
            path = stage / relative
            path.write_text(re.sub(pattern, replacement, path.read_text()))
    run(['flutter', 'pub', 'get'], stage / 'flutter', environment)
    arguments = [sys.executable, str(stage / 'build.py'), '--flutter']
    if args.hwcodec:
        arguments.append('--hwcodec')
    if args.unix_file_copy_paste:
        arguments.append('--unix-file-copy-paste')
    if args.package_format == 'msi':
        arguments.append('--skip-portable-pack')
    run(arguments, stage, environment)
    output = root / 'build/dist'
    output.mkdir(parents=True, exist_ok=True)
    version = re.search(r'^version\s*=\s*"([^"]+)"', (stage / 'Cargo.toml').read_text(), re.M)[1]
    slug = args.brand_name.lower()
    arch = 'arm64' if host == 'macos' and platform.machine().lower() in ('arm64', 'aarch64') else 'x86_64'
    destination = output / '{}-{}-{}{}.{}'.format(
        slug, version, arch, package_suffix(args.connection_role), args.package_format)
    if host == 'macos':
        app = stage / 'flutter/build/macos/Build/Products/Release' / (args.brand_name + '.app')
        with tempfile.TemporaryDirectory() as temporary:
            contents = Path(temporary) / 'Installer'
            contents.mkdir()
            shutil.copytree(str(app), str(contents / app.name), symlinks=True)
            finalize_macos_app(contents / app.name, stage, environment)
            (contents / 'Applications').symlink_to('/Applications')
            run(['hdiutil', 'create', '-volname', args.brand_name + ' Installer', '-srcfolder',
                 str(contents), '-ov', '-format', 'UDZO', str(destination)], stage, environment)
    elif args.package_format == 'msi':
        bundle = stage / 'flutter/build/windows/x64/runner/Release'
        msi = stage / 'res/msi'
        run([sys.executable, 'preprocess.py', '--app-name', args.brand_name,
             '--version', version, '-d', str(bundle)], msi, environment)
        run(['nuget', 'restore', 'msi.sln'], msi, environment)
        run(['msbuild', 'msi.sln', '-p:Configuration=Release', '-p:Platform=x64',
             '/p:TargetVersion=Windows10'], msi, environment)
        packages = list((msi / 'Package/bin').glob('*/Release/en-us/Package.msi'))
        if len(packages) != 1:
            raise RuntimeError('Expected one compiled Package.msi, found {}'.format(len(packages)))
        shutil.copy2(str(packages[0]), str(destination))
        if args.connection_role == 'host':
            from res.windows_host_setup import build_setup
            print('Host setup: ' + str(build_setup(destination, args.brand_name)), flush=True)
    else:
        source = stage / ('{}-{}-install.exe'.format(slug, version) if host == 'windows'
                          else '{}-{}.deb'.format(slug, version))
        shutil.copy2(str(source), str(destination))
    print('Package: ' + str(destination), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--platform', choices=tuple(FORMATS), required=True)
    parser.add_argument('--package-format', required=True)
    parser.add_argument('--brand-name', type=validate_brand_name, required=True)
    parser.add_argument('--hwcodec', action='store_true')
    parser.add_argument('--unix-file-copy-paste', action='store_true')
    add_arguments(parser)
    build(Path(__file__).resolve().parents[1], parser.parse_args())


if __name__ == '__main__':
    main()
