# Windows hosts and automatic pairing: regression surface

The minimization review compared the existing files against public source commit
`7040023acf4bd51446b361fd53db60d05e448fae`. The ordinary client path remains in
place when the connection role is `standard`, or when automatic pairing is not
configured. No remote desktop protocol or public rendezvous server changes were
needed.

| Existing file | Required change and affected path |
| --- | --- |
| `.github/workflows/branded-desktop.yml` | Supplies the pairing URL and role-specific build secrets, describes Windows hosts, and verifies installation only for a Windows host MSI. Standard packages skip that installation check. |
| `res/connection_role.py` | Accepts Windows MSI hosts, validates optional pairing settings, selects the matching token, and prepares the generated installer/configuration. Standard builds discard personal credentials; the Linux installation path remains intact. |
| `src/deployment.rs` | Routes the existing `--setup-host` command to the new Windows implementation. Linux setup is unchanged. |
| `src/platform/mod.rs` | Registers the Windows-only host setup module. |
| `src/lib.rs` | Registers the desktop-only pairing module. |
| `src/rendezvous_mediator.rs` | Adds a thin pairing startup hook beside existing background synchronization. It returns immediately unless this is an installed host with pairing configured. |
| `flutter/lib/desktop/deployment_profile.dart` | Adds empty default pairing constants; values are supplied only in generated personal build sources. |
| `flutter/lib/desktop/pages/connection_page.dart` | Shows the new computer list for a controller with pairing configured. The existing manual connection page remains the fallback. |
| `res/test_connection_role.py` | Covers Windows host MSI preparation and selection of separate host/controller tokens. |
| `docs/platform-builds.md` | Documents Windows host installation, automatic discovery and local backend deployment. |

New implementation lives in `src/platform/windows_host.rs`, `src/pairing.rs`,
`flutter/lib/desktop/widgets/paired_hosts.dart`, `res/msi-host-setup.wxs`, and
`res/pairing/`. The WiX fragment and launch suppression are applied only to the
generated Windows host sources; the original MSI template is unchanged.

Validation completed locally: all 10 Python build/branding/role tests pass;
Rust `cargo check --locked --offline --features flutter --lib` passes on macOS;
Dart analysis of the affected controller files reports only the existing
`connection_page.dart` deprecation; the Worker passes JavaScript syntax checking.
The deployed backend passed health, authentication, separate token permissions,
temporary host registration, controller listing and deletion checks. Cloudflare
receives no desktop password. The temporary verification host was removed.

The Windows build workflow additionally installs the real MSI, checks automatic
service startup and the private connection profile, and reapplies the unattended
settings. A real desktop session must still be checked on the user's Windows
computer after installing the host and opening the Mac controller.

Known limits: computers must be awake and online; heartbeat recency does not
guarantee desktop reachability. These personal installers contain credentials and
are distributed through a private repository. macOS signing is ad hoc without
Apple notarization; Windows signing is not configured.

## One-click background host setup

The follow-up changes affect these existing files and paths only:

| Existing file | Required change and affected path |
| --- | --- |
| `res/ci_build.py` | Windows host MSI builds additionally package the MSI in a one-click EXE. Standard and controller builds follow their previous paths. |
| `res/connection_role.py` | Generated Windows host MSI sources default to no desktop/startup tray shortcut and suppress both application launch actions. Original MSI templates and other roles stay unchanged. |
| `res/test_connection_role.py` | Extends the existing Windows host preparation check to cover the requested shortcut and tray-launch defaults. |
| `.github/workflows/branded-desktop.yml` | Windows host validation launches the generated background setup EXE, checks for no desktop shortcut, and then performs the existing service/password checks. Other packages skip this step. |
| `docs/platform-builds.md` | Explains background setup, the required Windows administrator approval, and packaging an existing MSI. |
| `docs/automatic-pairing-review.md` | Records this required minimization review, affected paths, validation and limits. |

The separate `res/windows_host_setup.py`, C# bootstrapper and administrator
manifest contain the new packaging logic. The new
`.github/workflows/windows-host-setup.yml` packages an already released private
MSI and verifies native installation. No Rust application, remote desktop
protocol, pairing backend or Mac controller code changes are needed.

The one-click EXE hides installation UI after normal administrator approval.
It preserves Windows' installed-app entry and service visibility. If an earlier
MSI was already installed, setup removes the branded desktop and startup tray
shortcuts for the installing account and the shared Windows folders. A shortcut
manually placed in a different user's personal folders must be removed by that user.

Validation: all 10 Python build/branding/role checks pass. Windows run
`38071603762` successfully installed the setup EXE over the existing MSI and on a
fresh installation, checking no desktop/startup tray shortcut, no host window,
automatic service startup and the shared password. The MSI payload's original
filename is preserved and the installing account can read, but not modify, the
protected extracted payload. The setup EXE is distributed privately with its
SHA-256 checksum; it does not change the existing Mac controller.

Known CI limit: the system installation profile's public key can differ from the
user session's registration key, so deletion by the profile key can leave a test
computer in the registry. The test records from these runs were removed locally
by their exact name, ID and timestamp, preserving the user's real Windows host.

## Automatic MSI installation without the wizard

The follow-up changes are limited to Windows host packaging:

| Existing file | Required change and affected path |
| --- | --- |
| `res/msi-host-setup.wxs` | Adds `LIMITUI` to the host-only fragment so double-clicking uses basic progress UI without wizard pages; uses the existing required `ARPNOMODIFY` property and suppresses automatic reboot. The installed-app removal entry remains available. |
| `res/ci_build.py` | Returns the host MSI directly rather than automatically creating an EXE launcher. Standard, controller, Linux and macOS packages retain their existing paths; the separate EXE packaging workflow remains available. |
| `res/connection_role.py` | Reads the generated Windows host component and shortcut XML as UTF-8 with optional BOM before rewriting it. Windows' default ANSI decoding otherwise corrupts the BOM and directly prevents this MSI from compiling. Other role paths remain unchanged. |
| `.github/workflows/branded-desktop.yml` | Checks Windows host preparation before compilation, installs the Windows host MSI with the default UI selection and checks that its logged UI level is basic. Keeps the existing service, password and shortcut checks. |
| `res/test_connection_role.py` | Extends the existing Windows host preparation regression check to cover wizard-free MSI properties and valid generated XML, including on Windows. |
| `docs/platform-builds.md` | Documents double-click behavior, the remaining Windows progress/UAC UI, the fully silent command, and the unsigned publisher limitation. |
| `docs/automatic-pairing-review.md` | Records this minimization review and verification limits. |

No application, controller, pairing protocol or backend changes are required.
The host's existing generated shortcut defaults remain disabled; the ordinary
MSI template is unchanged. `LIMITUI` restricts installation to basic UI, not
fully silent UI. Fully silent MSI installation uses `/qn` from an administrator
command prompt. Neither option bypasses Windows security checks or signs the
application.

New implementation is confined to `res/windows_host_msi.py` and the separate
`windows-host-msi.yml` workflow. This optional packaging path verifies the old
private release checksum and edits installer properties/sequences without
changing the embedded application. New product/package codes support upgrading
the old MSI. The workflow checks both upgrade and fresh installation, including
basic UI, desktop/startup shortcut removal, unchanged executable hash, automatic
service startup, shared password, closed host window and repeated setup.

Validation: all 10 local Python build/branding/role tests pass. Full Windows run
`38080719165` compiled the application but found the Windows XML encoding error
during MSI packaging; the explicit UTF-8 reads and XML regression check address
that failure. Windows run
[`38084727422`](https://github.com/israel1281/ectron-personal-builds/actions/runs/38084727422)
passed the Windows XML preparation check and both native installation cases:
upgrade from the previous MSI and fresh installation. The default installation
logged basic UI level 3 with no wizard interaction; desktop/startup shortcuts and
host application windows were absent. The executable hash matched the original
payload, the service was running with automatic startup, the shared password
matched, and repeated host setup succeeded. Uninstallation also succeeded.

The runner uses Windows Server 2022. Smart App Control acceptance on Windows 11
and an actual remote screen session are not established by these installer tests.
