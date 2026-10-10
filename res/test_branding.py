import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from res.branding import build_brand, prepare_brand, validate_brand_name


ROOT = Path(__file__).resolve().parents[1]


class BrandingTests(unittest.TestCase):
    def test_platform_names_and_runtime_contracts(self):
        originals = {p: hashlib.sha256((ROOT / p).read_bytes()).digest() for p in (
            'build.py', 'Cargo.toml', 'Cargo.lock', 'libs/hbb_common/src/config.rs',
            'src/common.rs', 'src/lang.rs', 'src/lang/it.rs',
            'flutter/windows/runner/main.cpp', 'flutter/lib/web/bridge.dart')}
        with tempfile.TemporaryDirectory() as temporary:
            stage = prepare_brand(ROOT, 'AcmeDesk', temporary)

            def read(relative):
                return (stage / relative).read_text()

            self.assertIn('RwLock::new("AcmeDesk".to_owned())', read('libs/hbb_common/src/config.rs'))
            self.assertIn('eq("RustDesk")', read('src/common.rs'))
            self.assertIn('mainGetAppNameSync(hint: hint) != "RustDesk"', read('flutter/lib/web/bridge.dart'))
            self.assertEqual(read('src/lang.rs'), (ROOT / 'src/lang.rs').read_text())
            self.assertEqual(read('src/lang/it.rs'), (ROOT / 'src/lang/it.rs').read_text())
            self.assertEqual(read('Cargo.lock'), (ROOT / 'Cargo.lock').read_text())
            self.assertIn('https://github.com/rustdesk-org/rdev', read('Cargo.toml'))
            self.assertIn('name = "librustdesk"', read('Cargo.toml'))
            self.assertIn('name = "acmedesk"\npath = "src/main.rs"', read('Cargo.toml'))
            self.assertIn('rustdesk_core_main_args', read('flutter/windows/runner/main.cpp'))
            self.assertIn('LoadLibraryA("librustdesk.dll")', read('flutter/windows/runner/main.cpp'))
            self.assertIn('"ProductName", "AcmeDesk"', read('flutter/windows/runner/Runner.rc'))
            self.assertIn('PRODUCT_NAME = AcmeDesk', read('flutter/macos/Runner/Configs/AppInfo.xcconfig'))
            self.assertIn('com.carriez.acmedesk', read('flutter/macos/Runner/Configs/AppInfo.xcconfig'))
            self.assertIn('BuildableName = "AcmeDesk.app"', read('flutter/macos/Runner.xcodeproj/xcshareddata/xcschemes/Runner.xcscheme'))
            self.assertIn('com.carriez.AcmeDesk_service', read('src/platform/privileges_scripts/daemon.plist'))
            self.assertIn('set(BINARY_NAME "acmedesk")', read('flutter/linux/CMakeLists.txt'))
            self.assertIn('org.rustdesk.rustdesk/host', read('flutter/linux/my_application.cc'))
            self.assertIn('gtk_window_set_title(window, "AcmeDesk")', read('flutter/linux/my_application.cc'))
            self.assertIn('Exec=acmedesk %u', read('res/acmedesk.desktop'))
            self.assertIn('ExecStart=/usr/bin/acmedesk --service', read('res/acmedesk.service'))
            self.assertIn('/usr/share/acmedesk/acmedesk', read('res/DEBIAN/postinst'))
            self.assertIn('/usr/lib/acmedesk/libdrmtap.so.0', read('libs/scrap/src/common/drmtap_dl.rs'))
            self.assertIn('com.carriez.acmedesk', read('flutter/android/app/build.gradle'))
            self.assertIn('System.loadLibrary("rustdesk")', read('flutter/android/app/src/main/kotlin/ffi.kt'))
            self.assertIn('android:scheme="acmedesk"', read('flutter/android/app/src/main/AndroidManifest.xml'))
            self.assertIn('DEFAULT_NOTIFY_TITLE = "AcmeDesk"', read('flutter/android/app/src/main/kotlin/com/carriez/flutter_hbb/MainService.kt'))
            self.assertIn('<string>AcmeDesk</string>', read('flutter/ios/Runner/Info.plist'))
            self.assertIn('app_name == "RustDesk"', read('res/msi/preprocess.py'))
            self.assertIn('default="AcmeDesk"', read('res/msi/preprocess.py'))
            self.assertIn('f.write("rustdesk".encode', read('libs/portable/generate.py'))
            self.assertIn("if os.path.isfile('/usr/bin/pacman'):\n        return 'pacman'", read('build.py'))
            self.assertFalse((stage / 'res/rustdesk.desktop').exists())
            self.assertFalse((stage / 'build').exists())
            self.assertFalse(list(stage.rglob('.git')))
            for relative in ('build.py', 'res/branding.py', 'res/msi/preprocess.py'):
                ast.parse(read(relative), filename=relative)
            manifest = json.loads(read('.brand.json'))
            self.assertEqual(manifest['name'], 'AcmeDesk')
            self.assertIn('res/acmedesk.service', manifest['changed_files'])
        for relative, digest in originals.items():
            self.assertEqual(hashlib.sha256((ROOT / relative).read_bytes()).digest(), digest)

    def test_refresh_and_brand_isolation(self):
        with tempfile.TemporaryDirectory() as temporary:
            first = prepare_brand(ROOT, 'RustDesk-Admin', temporary)
            cache = first / 'target' / 'cache-marker'
            cache.parent.mkdir()
            cache.write_text('compiled for this brand')
            original_config = (first / 'libs/hbb_common/src/config.rs').read_bytes()
            refreshed = prepare_brand(ROOT, 'RustDesk-Admin', temporary)
            self.assertEqual(refreshed, first)
            self.assertEqual(cache.read_text(), 'compiled for this brand')
            self.assertEqual((first / 'libs/hbb_common/src/config.rs').read_bytes(), original_config)
            self.assertNotIn('RustDesk-Admin-Admin', (first / 'Cargo.toml').read_text())
            self.assertIn('customModule="RustDesk_Admin"', (first / 'flutter/macos/Runner/Base.lproj/MainMenu.xib').read_text())
            second = prepare_brand(ROOT, 'OtherDesk', temporary)
            self.assertNotEqual(first, second)
            self.assertFalse((second / 'target').exists())
            self.assertIn('"OtherDesk".to_owned()', (second / 'libs/hbb_common/src/config.rs').read_text())

    def test_cli_validation_and_build_dispatch(self):
        for name in ('../Bad', 'Desk Name', 'Desk;cmd', 'Desk_1', 'Desk应用', 'CON', 'COM1', ''):
            with self.subTest(name=name), self.assertRaises(argparse.ArgumentTypeError):
                validate_brand_name(name)
        args = argparse.Namespace(brand_name='AcmeDesk', prepare_brand_only=False, flutter=True)
        with tempfile.TemporaryDirectory() as temporary:
            stage = Path(temporary) / 'acmedesk'
            with patch('res.branding.prepare_brand', return_value=stage), patch('res.branding.subprocess.run') as run:
                run.return_value.returncode = 0
                code = build_brand(ROOT, args, ['--flutter', '--brand-name=AcmeDesk', '--hwcodec'])
                self.assertEqual(code, 0)
                self.assertEqual(run.call_args_list[0].args[0], ['flutter', 'pub', 'get'])
                self.assertEqual(run.call_args_list[1].args[0],
                                 [sys.executable, str(stage / 'build.py'), '--flutter', '--hwcodec'])
                self.assertEqual(run.call_args.kwargs['env']['CARGO_TARGET_DIR'], str(stage / 'target'))
                run.reset_mock()
                run.return_value.returncode = 17
                self.assertEqual(build_brand(ROOT, args, ['--flutter', '--brand-name', 'AcmeDesk']), 17)
                self.assertEqual(run.call_count, 1)
                if sys.platform == 'darwin':
                    flutter = Path(temporary) / 'development/flutter/bin/flutter'
                    flutter.parent.mkdir(parents=True)
                    flutter.write_text('#!/bin/sh\n')
                    flutter.chmod(0o755)
                    vcpkg = Path(temporary) / 'development/vcpkg'
                    (vcpkg / 'installed').mkdir(parents=True)
                    run.return_value.returncode = 0
                    with patch.dict(os.environ, {'HOME': temporary, 'PATH': os.defpath, 'VCPKG_ROOT': ''}):
                        self.assertEqual(build_brand(ROOT, args, ['--flutter', '--brand-name', 'AcmeDesk']), 0)
                    for call in run.call_args_list[-2:]:
                        self.assertEqual(shutil.which('flutter', path=call.kwargs['env']['PATH']), str(flutter))
                        self.assertEqual(call.kwargs['env']['VCPKG_ROOT'], str(vcpkg))
        for arguments in (['--prepare-brand-only'], ['--brand-name', '../Bad'],
                          ['--brand-name', 'AcmeDesk', '--skip-cargo']):
            result = subprocess.run([sys.executable, str(ROOT / 'build.py')] + arguments,
                                    cwd=str(ROOT), capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
        result = subprocess.run([sys.executable, str(ROOT / 'build.py'), '--flutter',
                                 '--brand-name', 'NoBuild', '--print-features'],
                                cwd=str(ROOT), capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, 'flutter\n')
        self.assertFalse((ROOT / 'build/brands/nobuild').exists())


if __name__ == '__main__':
    unittest.main()
