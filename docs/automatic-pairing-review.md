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
