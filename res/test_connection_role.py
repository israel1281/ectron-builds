import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from res.connection_role import prepare_role


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
                               'BUILD_REPOSITORY_PRIVATE': 'true'}
                args = argparse.Namespace(connection_role=role, platform=platform,
                                          package_format=package, host_id='', brand_name='ectron')
                prepare_role(stage, args, environment)
                self.assertEqual(json.loads(environment['ECTRON_DEPLOYMENT_PROFILE'])['password'], password)
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
