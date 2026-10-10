import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

from res.connection_role import prepare_role, validate_role


ROOT = Path(__file__).resolve().parents[1]


class ConnectionRoleTests(unittest.TestCase):
    def test_role_flags_accept_linux_host_and_controller_id_and_reject_unsupported_host(self):
        for platform, role in [('linux', 'host'), ('mac', 'controller'), ('windows', 'controller')]:
            args = [sys.executable, str(ROOT / 'build.py'), '--platform', platform,
                    '--connection-role', role, '--brand-name', 'ectron', '--dry-run']
            if role == 'controller':
                args += ['--host-id', '123456789']
            result = subprocess.run(args, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            settings = json.loads(result.stdout)
            self.assertEqual(settings['connection_role'], role)
        result = subprocess.run([sys.executable, str(ROOT / 'build.py'), '--platform', 'mac',
                                 '--connection-role', 'host', '--dry-run'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)

    def test_windows_host_msi_configures_service_without_launching_app(self):
        validate_role('host', 'windows', 'msi', '')
        with self.assertRaisesRegex(ValueError, 'Windows MSI'):
            validate_role('host', 'windows', 'exe', '')
        with tempfile.TemporaryDirectory() as temporary:
            stage = Path(temporary)
            for directory in ['flutter/lib/desktop', 'res/msi/Package/Fragments', 'res/msi/Package/Components']:
                (stage / directory).mkdir(parents=True)
            component = stage / 'res/msi/Package/Components/RustDesk.wxs'
            original = (ROOT / 'res/msi/Package/Components/RustDesk.wxs').read_text()
            component.write_text(original)
            (stage / 'res/msi-host-setup.wxs').write_text((ROOT / 'res/msi-host-setup.wxs').read_text())
            shortcuts = stage / 'res/msi/Package/Fragments/ShortcutProperties.wxs'
            shortcuts.write_text((ROOT / 'res/msi/Package/Fragments/ShortcutProperties.wxs').read_text())
            args = argparse.Namespace(connection_role='host', platform='windows', package_format='msi',
                                      host_id='', brand_name='ectron')
            prepare_role(stage, args, {'ECTRON_HOST_PASSWORD': 'private-password-1234'})
            fragment = (stage / 'res/msi/Package/Fragments/HostSetup.wxs').read_text()
            self.assertIn('ExeCommand="--setup-host"', fragment)
            self.assertIn('Return="check"', fragment)
            self.assertIn('Id="LIMITUI" Value="1"', fragment)
            self.assertIn('Id="REBOOT" Value="ReallySuppress"', fragment)
            self.assertIn('<CustomActionRef Id="ConfigureHost" />', component.read_text())
            self.assertIn('Action="LaunchApp" After="InstallFinalize" Condition="0"', component.read_text())
            self.assertIn('Action="LaunchAppTray" After="InstallFinalize" Condition="0"', component.read_text())
            self.assertIn('Id="DESKTOPSHORTCUTS" Value="0"', shortcuts.read_text())
            self.assertIn('Id="CREATEDESKTOPSHORTCUTS" Value="0"', shortcuts.read_text())
            self.assertIn('Id="STARTUPSHORTCUTS" Value="0"', shortcuts.read_text())
            ET.fromstring(shortcuts.read_bytes())
            ET.fromstring(component.read_bytes())
            self.assertEqual((ROOT / 'res/msi/Package/Components/RustDesk.wxs').read_text(), original)

    def test_personal_packages_use_the_same_secret_without_modifying_default_sources(self):
        password = 'private-$password-1234'
        with tempfile.TemporaryDirectory() as temporary:
            stage = Path(temporary)
            (stage / 'res/DEBIAN').mkdir(parents=True)
            (stage / 'flutter/lib/desktop').mkdir(parents=True)
            (stage / 'res/DEBIAN/postinst').write_text('#!/bin/bash\nset -e\n')
            (stage / 'res/host-postinst.sh').write_text((ROOT / 'res/host-postinst.sh').read_text())
            default = (ROOT / 'flutter/lib/desktop/deployment_profile.dart').read_text()
            for role, platform, package in [('host', 'linux', 'deb'), ('controller', 'macos', 'dmg')]:
                (stage / 'flutter/lib/desktop/deployment_profile.dart').write_text(default)
                environment = {'ECTRON_HOST_PASSWORD': password, 'GITHUB_ACTIONS': 'true',
                               'BUILD_REPOSITORY_PRIVATE': 'true',
                               'ECTRON_PAIRING_URL': 'https://pairing.example.com',
                               'ECTRON_PAIRING_HOST_TOKEN': 'h' * 43,
                               'ECTRON_PAIRING_CONTROLLER_TOKEN': 'c' * 43}
                args = argparse.Namespace(connection_role=role, platform=platform,
                                          package_format=package, host_id='', brand_name='ectron')
                prepare_role(stage, args, environment)
                profile = json.loads(environment['ECTRON_DEPLOYMENT_PROFILE'])
                self.assertEqual(profile['password'], password)
                self.assertEqual(profile['pairing_token'], ('h' if role == 'host' else 'c') * 43)
                self.assertNotIn('ECTRON_PAIRING_HOST_TOKEN', environment)
                self.assertNotIn('ECTRON_PAIRING_CONTROLLER_TOKEN', environment)
                self.assertNotIn('ECTRON_HOST_PASSWORD', environment)
                self.assertIn(r'private-\$password-1234', (stage / 'flutter/lib/desktop/deployment_profile.dart').read_text())
            postinst = (stage / 'res/DEBIAN/postinst').read_text()
            self.assertIn('/usr/bin/ectron --setup-host', postinst)
            self.assertNotIn(password, postinst)
            self.assertEqual(subprocess.run(['bash', '-n', str(stage / 'res/DEBIAN/postinst')]).returncode, 0)
            self.assertEqual((ROOT / 'flutter/lib/desktop/deployment_profile.dart').read_text(), default)
            with self.assertRaisesRegex(ValueError, 'private build repository'):
                prepare_role(stage, args, {'ECTRON_HOST_PASSWORD': password, 'GITHUB_ACTIONS': 'true',
                                           'BUILD_REPOSITORY_PRIVATE': 'false'})


if __name__ == '__main__':
    unittest.main()
