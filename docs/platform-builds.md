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

Open the DMG on your Mac and drag the app into Applications. Copy the DEB to the
Linux computer, then install it there with `sudo apt install ./ectron-1.5.0-x86_64.deb`.
On Windows, open the generated EXE or MSI to install the client.

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
