"""Prepare personal host/controller packages without putting credentials in source."""

import json
import re


ROLES = ('standard', 'host', 'controller')


def add_arguments(parser):
    parser.add_argument('--connection-role', choices=ROLES, default='standard',
                        help='host: unattended Linux computer; controller: control other computers.')
    parser.add_argument('--host-id', default='',
                        help='Existing host device ID to prefill in a controller build.')


def validate_role(role, platform, package, host_id):
    if role == 'host' and (platform != 'linux' or package != 'deb'):
        raise ValueError('Automatic host installation currently requires Linux DEB.')
    if host_id and (role != 'controller' or not re.fullmatch(r'[0-9]{6,16}', host_id)):
        raise ValueError('--host-id requires a controller build and a numeric device ID.')


def prepare_role(stage, args, environment):
    role = args.connection_role
    validate_role(role, args.platform, args.package_format, args.host_id)
    if role == 'standard':
        environment.pop('ECTRON_DEPLOYMENT_PROFILE', None)
        environment.pop('ECTRON_HOST_PASSWORD', None)
        return
    password = environment.pop('ECTRON_HOST_PASSWORD', '')
    if not 12 <= len(password) <= 128 or '\n' in password or '\r' in password:
        raise ValueError('Set ECTRON_HOST_PASSWORD to a shared password of 12–128 characters.')
    if environment.get('GITHUB_ACTIONS') == 'true' and environment.get('BUILD_REPOSITORY_PRIVATE') != 'true':
        raise ValueError('Personal installers contain a password and require a private build repository.')
    profile = {'role': role, 'password': password, 'host_id': args.host_id}
    environment['ECTRON_DEPLOYMENT_PROFILE'] = json.dumps(profile, ensure_ascii=True)
    dart = stage / 'flutter/lib/desktop/deployment_profile.dart'
    def literal(value):
        return json.dumps(value, ensure_ascii=True).replace('$', '\\$')
    dart.write_text('const deploymentRole = {};\nconst deploymentPassword = {};\n'
                    'const deploymentHostId = {};\n'.format(
                        literal(role), literal(password), literal(args.host_id)), encoding='utf-8')
    if role == 'host':
        postinst = stage / 'res/DEBIAN/postinst'
        script = (stage / 'res/host-postinst.sh').read_text()
        postinst.write_text(postinst.read_text() + '\n' + script.replace(
            '@BINARY@', args.brand_name.lower()), encoding='utf-8')


def package_suffix(role):
    return '' if role == 'standard' else '-' + role
