"""Deploy the pairing service locally with Cloudflare account credentials."""

import json
import os
from pathlib import Path
import re
import subprocess
import urllib.request


def main():
    root = Path(__file__).resolve().parents[2]
    account = os.environ['CLOUDFLARE_ACCOUNT_ID']
    name = os.environ['ECTRON_PAIRING_WORKER_NAME']
    token = os.environ['CLOUDFLARE_API_TOKEN']
    if not re.fullmatch(r'ectron-personal-pairing-[a-f0-9]{8}', name):
        raise ValueError('Use a dedicated ectron personal pairing Worker name.')

    def api(endpoint, body=None):
        request = urllib.request.Request(
            'https://api.cloudflare.com/client/v4/accounts/' + account + '/' + endpoint,
            data=json.dumps(body).encode() if body is not None else None,
            headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.load(response)
        if not result.get('success'):
            raise RuntimeError('Cloudflare API operation failed')
        return result['result']

    databases = api('d1/database?per_page=100')
    database = next((item for item in databases if item['name'] == name), None)
    if database is None:
        database = api('d1/database', {'name': name})
    database_id = database['uuid']
    api('d1/database/' + database_id + '/query', {
        'sql': (root / 'res/pairing/schema.sql').read_text(),
    })
    directory = root / 'build/pairing-worker'
    directory.mkdir(parents=True, exist_ok=True)
    config = directory / 'wrangler.json'
    config.write_text(json.dumps({
        'name': name, 'main': str(root / 'res/pairing/worker.mjs'),
        'account_id': account, 'compatibility_date': '2026-10-10', 'workers_dev': True,
        'd1_databases': [{'binding': 'DB', 'database_name': name, 'database_id': database_id}],
    }, indent=2))
    command = ['npx', '--yes', 'wrangler@4.149.0']
    deployed = subprocess.run(command + ['deploy', '--config', str(config)],
                              check=True, capture_output=True, text=True)
    print(deployed.stdout)
    urls = re.findall(r'https://[a-z0-9.-]+\.workers\.dev', deployed.stdout)
    if not urls:
        raise RuntimeError('Deployment did not return its Workers URL')
    url = urls[-1]
    secrets = {'ENROLL_TOKEN': os.environ['ECTRON_PAIRING_HOST_TOKEN'],
               'CONTROLLER_TOKEN': os.environ['ECTRON_PAIRING_CONTROLLER_TOKEN']}
    subprocess.run(command + ['secret', 'bulk', '--config', str(config)],
                   input=json.dumps(secrets), text=True, check=True)
    (root / 'build/pairing-deployment.json').write_text(json.dumps({
        'url': url, 'worker': name, 'database_id': database_id,
    }, indent=2) + '\n')
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a') as file:
            file.write('Automatic pairing service deployed: ' + url + '\n')


if __name__ == '__main__':
    main()
