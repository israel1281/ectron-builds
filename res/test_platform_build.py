import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from res.ci_build import finalize_macos_app, run
from res.platform_build import copy_snapshot


ROOT = Path(__file__).resolve().parents[1]


class PlatformBuildTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == 'darwin', 'Requires macOS codesign')
    def test_mac_signature_includes_service_added_after_xcode_build(self):
        with tempfile.TemporaryDirectory() as temporary:
            app = Path(temporary) / 'Client.app'
            binaries = app / 'Contents/MacOS'
            binaries.mkdir(parents=True)
            (app / 'Contents/Info.plist').write_bytes(plistlib.dumps({
                'CFBundleIdentifier': 'com.example.client', 'CFBundleExecutable': 'client',
                'CFBundlePackageType': 'APPL'}))
            source = Path(temporary) / 'client.c'
            source.write_text('#ifdef LIBRARY\nint value(void) { return 0; }\n#else\n'
                              'int value(void); int main(void) { return value(); }\n#endif\n')
            library = app / 'Contents/Frameworks/client.dylib'
            library.parent.mkdir()
            subprocess.run(['clang', '-dynamiclib', '-DLIBRARY', str(source),
                            '-o', str(library)], check=True)
            subprocess.run(['clang', str(source), str(library), '-o', str(binaries / 'client')], check=True)
            subprocess.run(['codesign', '--sign', '-', '--force', '--options=runtime', str(app)], check=True)
            shutil.copy2(str(binaries / 'client'), str(binaries / 'service'))
            verify = ['codesign', '--verify', '--deep', '--strict', str(app)]
            self.assertNotEqual(subprocess.run(verify, capture_output=True).returncode, 0)
            finalize_macos_app(app, Path(temporary), os.environ.copy())
            self.assertEqual(subprocess.run(verify, capture_output=True).returncode, 0)
            self.assertEqual(subprocess.run([str(binaries / 'client')], capture_output=True).returncode, 0)

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
