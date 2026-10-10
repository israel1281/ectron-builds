"""Embed a host MSI in a one-click, elevated Windows GUI executable."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

from res.branding import validate_brand_name


def build_setup(msi, brand):
    msi = Path(msi).resolve()
    validate_brand_name(brand)
    if os.name != 'nt':
        raise ValueError('Build the host setup executable on Windows.')
    if not msi.name.endswith('-host.msi'):
        raise ValueError('Provide a personal host MSI, ending in -host.msi.')
    digest = hashlib.sha256()
    with msi.open('rb') as source:
        if source.read(8) != bytes.fromhex('d0cf11e0a1b11ae1'):
            raise ValueError('The payload is not a Windows Installer container.')
        source.seek(0)
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    output = msi.with_name(msi.stem + '-setup.exe')
    resources = Path(__file__).resolve().parent
    compiler = Path(os.environ['SystemRoot']) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
    source = (resources / 'windows-host-setup.cs').read_text(encoding='utf-8').replace(
        '@BRAND@', json.dumps(brand)).replace('@MSI_SHA256@', json.dumps(digest.hexdigest()))
    with tempfile.TemporaryDirectory() as temporary:
        generated = Path(temporary) / 'HostSetup.cs'
        generated.write_text(source, encoding='utf-8')
        subprocess.run([str(compiler), '/nologo', '/target:winexe', '/platform:x64', '/optimize+',
                        '/reference:System.Windows.Forms.dll',
                        '/win32manifest:' + str(resources / 'windows-host-setup.manifest'),
                        '/resource:' + str(msi) + ',HostMsi', '/out:' + str(output), str(generated)], check=True)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--msi', type=Path, required=True)
    parser.add_argument('--brand-name', type=validate_brand_name, required=True)
    args = parser.parse_args()
    print('Host setup: ' + str(build_setup(args.msi, args.brand_name)), flush=True)


if __name__ == '__main__':
    main()
