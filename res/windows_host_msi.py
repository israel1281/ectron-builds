"""Repackage a personal host MSI with its standard wizard and installer logging.

Run on Windows with Python 3.11, whose standard library exposes the MSI API.
"""

import argparse
import os
from pathlib import Path
import shutil


def configure_msi(source, output):
    if os.name != 'nt':
        raise ValueError('Repackage the host MSI on Windows with Python 3.11.')
    import msilib

    source, output = Path(source).resolve(), Path(output).resolve()
    if not source.name.endswith('-host.msi') or source.name != output.name or source == output:
        raise ValueError('Copy a personal -host.msi to another directory with the same filename.')
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, output)
    database = msilib.OpenDatabase(str(output), msilib.MSIDBOPEN_TRANSACT)
    try:
        view = database.OpenView("SELECT `Action` FROM `CustomAction` WHERE `Action` = 'ConfigureHost'")
        view.Execute(None)
        host_action = view.Fetch()
        view.Close()
        if host_action is None:
            raise ValueError('The MSI must already contain the unattended host setup action.')

        view = database.OpenView("DELETE FROM `Property` WHERE `Property` = 'LIMITUI'")
        view.Execute(None)
        view.Close()
        properties = {'MsiLogging': 'voicewarmup', 'ARPNOMODIFY': '1', 'REBOOT': 'ReallySuppress',
                      'DESKTOPSHORTCUTS': '0', 'CREATEDESKTOPSHORTCUTS': '0',
                      'STARTUPSHORTCUTS': '0', 'LAUNCH_TRAY_APP': 'N',
                      'ProductCode': msilib.gen_uuid()}
        view = database.OpenView('SELECT `Property`, `Value` FROM `Property`')
        view.Execute(None)
        for name, value in properties.items():
            row = msilib.CreateRecord(2)
            row.SetString(1, name)
            row.SetString(2, value)
            view.Modify(msilib.MSIMODIFY_ASSIGN, row)
        view.Close()
        view = database.OpenView("UPDATE `InstallExecuteSequence` SET `Condition` = '0' "
                                 "WHERE `Action` = 'LaunchApp' OR `Action` = 'LaunchAppTray'")
        view.Execute(None)
        view.Close()
        summary = database.GetSummaryInformation(1)
        summary.SetProperty(msilib.PID_REVNUMBER, msilib.gen_uuid())
        summary.Persist()
        database.Commit()
    finally:
        database.Close()
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--msi', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print('Host MSI with setup wizard: ' + str(configure_msi(args.msi, args.output)))


if __name__ == '__main__':
    main()
