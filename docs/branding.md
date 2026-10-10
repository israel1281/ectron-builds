# Building with your brand name

Pass the app name to the existing desktop build script:

```sh
python3 build.py --flutter --brand-name AcmeDesk
```

Other build flags, such as `--hwcodec`, `--portable` and `--drm`, work with this
flag on their supported platforms. Without `--brand-name`, the existing RustDesk
build runs as before. Names must start with an ASCII letter, use letters, digits
and hyphens, and be at most 50 characters long. For example, `AcmeDesk` and
`AcmeDesk-Pro` work. Names containing spaces are unsupported by the existing
installer and service naming rules.

The script prepares an independent source tree in `build/brands/acmedesk/`, then
builds there. It uses `AcmeDesk` as the display name and `acmedesk` for executable,
package and URI names. Your original sources keep their default branding. Each
brand has its own Cargo and Flutter build outputs; preparing the same brand again
refreshes its sources and preserves its build caches.

The name controls the central runtime app name, translated app labels, window
titles, settings and log directories, desktop executable and installer filenames,
Linux launchers and services, Windows product metadata, macOS app bundle names and
identifiers, deep links, and mobile app labels and installed identifiers. Windows
MSI preparation also defaults to the selected name and uses its existing custom
brand logic.

Cargo crate names, FFI/JNI interfaces, driver identifiers, protocol keys,
translation keys, dependency URLs, server addresses, upstream links, icons and
copyright/license attribution retain their existing values. A name alone does
not provide replacement artwork, websites, signing identities or a server
configuration.

## Output locations

Paths are relative to `build/brands/acmedesk/`:

| Build | Output |
| --- | --- |
| Flutter macOS | `flutter/build/macos/Build/Products/Release/AcmeDesk.app` |
| Flutter Windows | `flutter/build/windows/<arch>/runner/Release/acmedesk.exe` |
| Windows EXE installer | `acmedesk-<version>-install.exe` |
| Flutter Linux | `flutter/build/linux/<arch>/release/bundle/` |
| Debian package | `acmedesk-<version>.deb` |
| Native Linux executable | `target/release/acmedesk` |
| Native Windows executable | `target/release/AcmeDesk.exe` |

Platform dependencies are the same as the upstream build. Flutter builds first
run `flutter pub get` inside the branded tree to generate its package paths.
The branding flag must compile its native code, so it cannot be combined directly
with `--skip-cargo` or `--package`: those could otherwise package an existing
RustDesk library under a new filename.

## Prepare sources without compiling

```sh
python3 build.py --brand-name AcmeDesk --prepare-brand-only
```

The generated `.brand.json` lists the name and every file changed in the copy.
You can review those files, or build them with existing Android, iOS, MSI or CI
commands. Run those commands from the generated tree and compile its Rust core
there as well. Existing CI workflows are not rewritten automatically.

For example, after compiling the branded Rust core for your Android targets and
copying its libraries to the generated Android project:

```sh
cd build/brands/acmedesk/flutter
flutter pub get
flutter build apk --release
```

For a workflow that builds Rust separately, prepare the brand, compile its
sources, then run `python3 build.py --flutter --skip-cargo` from
`build/brands/acmedesk/`. Windows MSI builds use the existing
`res/msi/preprocess.py` and Visual Studio workflow from that same tree.

Branding verification can be run without native build dependencies:

```sh
python3 -m unittest res.test_branding
```
