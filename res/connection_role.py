"""Prepare personal host/controller packages without putting credentials in source."""

import json
import re
from urllib.parse import urlsplit


ROLES = ('standard', 'host', 'controller')


def add_arguments(parser):
    parser.add_argument('--connection-role', choices=ROLES, default='standard',
                        help='host: unattended Linux/Windows computer; controller: control other computers.')
    parser.add_argument('--host-id', default='',
                        help='Existing host device ID to prefill in a controller build.')


def validate_role(role, platform, package, host_id):
    if role == 'host' and (platform, package) not in {('linux', 'deb'), ('windows', 'msi')}:
        raise ValueError('Automatic host installation requires Linux DEB or Windows MSI.')
    if host_id and (role != 'controller' or not re.fullmatch(r'[0-9]{6,16}', host_id)):
        raise ValueError('--host-id requires a controller build and a numeric device ID.')


def prepare_role(stage, args, environment):
    role = args.connection_role
    validate_role(role, args.platform, args.package_format, args.host_id)
    if role == 'standard':
        environment.pop('ECTRON_DEPLOYMENT_PROFILE', None)
        environment.pop('ECTRON_HOST_PASSWORD', None)
        for name in ('ECTRON_PAIRING_URL', 'ECTRON_PAIRING_HOST_TOKEN', 'ECTRON_PAIRING_CONTROLLER_TOKEN'):
            environment.pop(name, None)
        return
    password = environment.pop('ECTRON_HOST_PASSWORD', '')
    if not 12 <= len(password) <= 128 or '\n' in password or '\r' in password:
        raise ValueError('Set ECTRON_HOST_PASSWORD to a shared password of 12–128 characters.')
    if environment.get('GITHUB_ACTIONS') == 'true' and environment.get('BUILD_REPOSITORY_PRIVATE') != 'true':
        raise ValueError('Personal installers contain a password and require a private build repository.')
    pairing_url = environment.pop('ECTRON_PAIRING_URL', '').rstrip('/')
    host_token = environment.pop('ECTRON_PAIRING_HOST_TOKEN', '')
    controller_token = environment.pop('ECTRON_PAIRING_CONTROLLER_TOKEN', '')
    pairing_token = host_token if role == 'host' else controller_token
    if pairing_url:
        url = urlsplit(pairing_url)
        if (url.scheme != 'https' or not url.hostname or url.username or url.password
                or url.query or url.fragment or url.path not in ('', '/')):
            raise ValueError('ECTRON_PAIRING_URL must be an HTTPS origin.')
        if not re.fullmatch(r'[A-Za-z0-9_-]{32,128}', pairing_token):
            raise ValueError('Set the matching ECTRON_PAIRING_HOST_TOKEN or ECTRON_PAIRING_CONTROLLER_TOKEN secret.')
    profile = {'role': role, 'password': password, 'host_id': args.host_id,
               'pairing_url': pairing_url, 'pairing_token': pairing_token}
    environment['ECTRON_DEPLOYMENT_PROFILE'] = json.dumps(profile, ensure_ascii=True)
    dart = stage / 'flutter/lib/desktop/deployment_profile.dart'
    def literal(value):
        return json.dumps(value, ensure_ascii=True).replace('$', '\\$')
    dart.write_text('const deploymentRole = {};\nconst deploymentPassword = {};\n'
                    'const deploymentHostId = {};\nconst deploymentPairingUrl = {};\n'
                    'const deploymentPairingToken = {};\n'.format(
                        literal(role), literal(password), literal(args.host_id),
                        literal(pairing_url if role == 'controller' else ''),
                        literal(pairing_token if role == 'controller' else '')), encoding='utf-8')
    if role == 'host' and args.platform == 'linux':
        postinst = stage / 'res/DEBIAN/postinst'
        script = (stage / 'res/host-postinst.sh').read_text()
        postinst.write_text(postinst.read_text() + '\n' + script.replace(
            '@BINARY@', args.brand_name.lower()), encoding='utf-8')
    if role == 'host' and args.platform == 'windows':
        fragment = stage / 'res/msi/Package/Fragments/HostSetup.wxs'
        fragment.write_text((stage / 'res/msi-host-setup.wxs').read_text(), encoding='utf-8')
        component = stage / 'res/msi/Package/Components/RustDesk.wxs'
        component.write_text(re.sub(
            r'(<Custom Action="LaunchApp(?:Tray)?"[^>]*Condition=")[^"]*', r'\g<1>0',
            component.read_text()).replace(
                '<Fragment>', '<Fragment>\n\t\t<CustomActionRef Id="ConfigureHost" />', 1),
            encoding='utf-8')
        shortcuts = stage / 'res/msi/Package/Fragments/ShortcutProperties.wxs'
        shortcuts.write_text(shortcuts.read_text().replace(
            'Id="DESKTOPSHORTCUTS" Value="1"', 'Id="DESKTOPSHORTCUTS" Value="0"').replace(
            'Id="STARTUPSHORTCUTS" Value="1"', 'Id="STARTUPSHORTCUTS" Value="0"').replace(
            'Id="CREATEDESKTOPSHORTCUTS" Secure="yes"',
            'Id="CREATEDESKTOPSHORTCUTS" Value="0" Secure="yes"'), encoding='utf-8')


def package_suffix(role):
    return '' if role == 'standard' else '-' + role
