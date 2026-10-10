# Build desktop packages from your Mac

The `--platform` flag sends the current source snapshot to GitHub Actions. A native
macOS, Windows or Linux runner compiles it, packages it and returns the result.
You can start every build from the same Mac without copying source manually.
Flutter desktop compilation needs the target operating system's toolchain; these
commands use hosted runners rather than cross-compiling Windows on macOS.

## One-time GitHub setup

Install GitHub CLI and sign in with workflow access:

```sh
brew install gh
gh auth login --hostname github.com --git-protocol https --web
```

Create a dedicated empty build repository. For this setup the requested public
repository is `israel1281/ectron-builds`:

```sh
gh repo create israel1281/ectron-builds --public
```

The first build uploads a fresh source snapshot to `main`. Later builds use
separate `codex/build-…` branches. The workflow must exist on the default branch
for GitHub to accept dispatches. An existing repository without this workflow is
rejected rather than overwritten. The local source directory gets no `.git` folder.
The snapshot includes `libs/hbb_common` directly, so no submodule checkout is needed.

## Build commands

Run from the source directory. The first command saves the repository choice in
`build/github.json`; subsequent commands can omit `--github-repo`.

```sh
# Windows installer EXE, x86-64
python3 build.py --platform windows --package-format exe --brand-name ectron \
  --github-repo israel1281/ectron-builds

# Windows MSI, x86-64
python3 build.py --platform windows --package-format msi --brand-name ectron

# macOS DMG, Apple Silicon, minimum macOS 12.3
python3 build.py --platform mac --package-format dmg --brand-name ectron

# Ubuntu/Debian Linux DEB, x86-64
python3 build.py --platform linux --package-format deb --brand-name ectron
```

`--flutter` is implicit with `--platform`. Omitting `--brand-name` selects RustDesk.
Omitting `--package-format` selects DMG, EXE or DEB for the chosen platform.
`--hwcodec` enables the checkout's hardware codec feature and its additional
native dependencies. `--unix-file-copy-paste` is available for macOS/Linux.
Other advanced native build flags are rejected in the hosted build path.

The command waits for completion and downloads the package into
`build/artifacts/<brand>/<platform>/<run-id>/`. It prints the build URL so you can
watch progress and inspect errors. Interrupted waiting does not stop a cloud build:

```sh
gh run list --repo israel1281/ectron-builds
gh run watch RUN_ID --repo israel1281/ectron-builds --exit-status
gh run download RUN_ID --repo israel1281/ectron-builds --dir build/downloads
```

Use `--no-wait` to submit and return the URL immediately. Use `--dry-run` to inspect
the selected settings without uploading or compiling. GitHub retains the package
artifacts for 14 days. The workflow does not configure Windows Authenticode or
Apple Developer ID signing/notarization; public distribution needs a separate
signing setup.

macOS packaging signs the service and then seals the complete app after all build
steps. It verifies the app with `codesign --verify --deep --strict` before creating
the DMG. This fixes the invalid signature caused by adding the service after
Xcode's signing step. The signature is ad hoc; it does not provide Apple Developer
ID identity or notarization.

If macOS blocks this self-built app after downloading it, first check its signature:

```sh
codesign --verify --deep --strict --verbose=2 /Applications/ectron.app
```

If that succeeds, use System Settings > Privacy & Security > Open Anyway when
available. For this project's verified ad hoc build, an alternative is to remove
the download quarantine from this app only:

```sh
xattr -rd com.apple.quarantine /Applications/ectron.app
open /Applications/ectron.app
```

Developer ID signing and notarization are needed for normal public distribution
without this manual approval. See [Apple's app security guidance](https://support.apple.com/102445).

Open the DMG on your Mac and drag the app into Applications. Copy the DEB to the
Linux computer, then install it there with `sudo apt install ./ectron-1.5.0-x86_64.deb`.
On Windows, open the generated EXE or MSI to install the client.

## Personal host and controller installers

`--connection-role host` makes a Linux DEB or Windows MSI install the shared permanent password,
accept connections by password, allow access while its window is closed, enable
keyboard/mouse control, and enable/start its background service. The installer waits
for the service to acknowledge its settings. Linux failures leave the package
unconfigured and print a retry command; Windows setup failures fail the MSI
installation. Upgrades reapply the shared password.
The application does not need to be opened on the host computer. The Windows MSI
does not launch the application window after installation.

`--connection-role controller` makes a Mac, Windows or Linux client use the same
password when you click Connect. `--host-id` optionally prefills an existing
host's numeric ID. An omitted ID lets you connect to any of your hosts by ID.
Ordinary builds default to `standard` and retain their previous behavior.

The shared password is read from the **ECTRON_HOST_PASSWORD** GitHub repository
secret, never a workflow input, committed source file or log. Set it in the private build
repository under Settings → Secrets and variables → Actions. Use 12–128
characters. Host and controller installers contain this credential and must be
distributed privately; public repositories reject personal builds. Public
source and standard installers may remain in `israel1281/ectron-builds`.

```sh
python3 build.py --platform linux --package-format deb --brand-name ectron \
  --connection-role host --github-repo OWNER/PRIVATE-BUILD-REPO

python3 build.py --platform windows --package-format msi --brand-name ectron \
  --connection-role host --github-repo OWNER/PRIVATE-BUILD-REPO

python3 build.py --platform mac --package-format dmg --brand-name ectron \
  --connection-role controller --github-repo OWNER/PRIVATE-BUILD-REPO

python3 build.py --platform windows --package-format msi --brand-name ectron \
  --connection-role controller --host-id YOUR_EXISTING_NUMERIC_HOST_ID \
  --github-repo OWNER/PRIVATE-BUILD-REPO
```

In GitHub's Run workflow form, choose the same `connection_role` and optionally
set `host_id`. Personal package filenames end in `-host` or `-controller`.
The public connection service gives each host its own device ID after install;
one ID cannot identify several different computers. Retaining the app's local
configuration retains its ID, subject to public-server registration/collisions.

For manual pairing, the installer saves a private connection profile at
`/var/lib/ectron/host-connection.json` on Linux or
`C:\ProgramData\ectron\host\host-connection.json` on Windows. Copy this file
privately to your Mac/Windows computer, then click **Import host connection** in
the controller build to connect using its ID and password. Alternatively, enter
its printed ID and click Connect; the controller already has the shared password.
Keep the connection profile private, since it contains the password.

### Automatic pairing through Cloudflare

The personal build repository is `israel1281/ectron-personal-builds`. Its
`ECTRON_PAIRING_URL` Actions variable points to
`https://ectron-personal-pairing-85247689.reload-proxy.workers.dev`. Two Actions
secrets, `ECTRON_PAIRING_HOST_TOKEN` and `ECTRON_PAIRING_CONTROLLER_TOKEN`, provide
separate credentials for registering hosts and listing computers. The Worker
stores the matching values as `ENROLL_TOKEN` and `CONTROLLER_TOKEN`. The shared
desktop password stays in the private installers and is not sent to Cloudflare.

With these settings, install the **host MSI** on Windows with administrator
approval. Its automatic service registers the computer's name and device ID
after its unattended settings and public-server registration are ready, and
refreshes registration every minute. On the Mac, install/open the **controller
DMG**. **My computers** refreshes every 15 seconds. Click **Connect** beside the
Windows computer; its ID and the shared password are supplied automatically.
No host application window or ID copying is required. Initial registration can
take a minute or longer depending on network availability.

Cloudflare only provides the computer registry. Remote desktop sessions continue
using the existing RustDesk rendezvous/relay service. The Windows computer must
be powered on, awake and online. A recent registry heartbeat is not a guarantee
that its desktop is reachable.

The backend source is in `res/pairing/`. `deploy.py` deploys locally using
`CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN`,
`ECTRON_PAIRING_WORKER_NAME`, `ECTRON_PAIRING_HOST_TOKEN`, and
`ECTRON_PAIRING_CONTROLLER_TOKEN` from the process environment. It creates a
dedicated D1 database, installs `schema.sql`, deploys the Worker and sets its two
limited secrets. Keep Cloudflare management credentials on the deployment
machine. Host and controller builds only need the limited pairing tokens.

Hosts must remain powered on, awake and online. GNOME Wayland can require local
screen-sharing approval; X11 is required to control the login screen after a
reboot. These installers do not bypass desktop permission prompts or change GDM.
See [RustDesk's Linux guide](https://rustdesk.com/docs/en/client/linux/).

## Local macOS build and libyuv

The original command still compiles locally:

```sh
python3 build.py --flutter --brand-name ectron
```

`libs/scrap/build.rs` looks in vcpkg when `VCPKG_ROOT` is set, otherwise it tries
Homebrew on Apple Silicon. This checkout needs libyuv, libvpx, aom and opus. The
standard Homebrew catalog does not provide libyuv. Use the pinned vcpkg checkout:

```sh
export VCPKG_ROOT="$HOME/development/vcpkg"
export PATH="$HOME/development/flutter/bin:$HOME/development/nasm/nasm-2.16.03:$PATH"
"$VCPKG_ROOT/vcpkg" install libyuv libvpx aom opus --classic --triplet arm64-osx \
  --overlay-ports="$PWD/res/vcpkg" --overlay-triplets="$PWD/res/vcpkg-triplets"
```

vcpkg is pinned to `9e593bb18ea69cc5095e012465dcd675a822ed0d`, matching this
checkout's CI. Branded Mac builds automatically discover
`~/development/vcpkg` and `~/development/flutter` when the environment does not
already specify them. Full Xcode and generated Flutter Rust bridge files are also
required for local builds. Hosted builds install the native tools and generate the
bridge automatically, so you can use the macOS platform flag before installing
full Xcode on this Mac.

References: [Flutter desktop setup](https://docs.flutter.dev/platform-integration/desktop),
[GitHub hosted runners](https://docs.github.com/en/actions/reference/runners/github-hosted-runners),
[GitHub CLI workflow dispatch](https://cli.github.com/manual/gh_workflow_run).
