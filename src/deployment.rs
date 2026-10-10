#[cfg(target_os = "linux")]
#[derive(serde_derive::Deserialize)]
struct Profile {
    role: String,
    password: String,
}

pub fn setup_command(args: &[String]) -> Option<i32> {
    if args.first().map(String::as_str) != Some("--setup-host") {
        return None;
    }
    if args.len() != 1 {
        eprintln!("Usage: --setup-host");
        return Some(1);
    }
    match setup_host() {
        Ok(()) => Some(0),
        Err(err) => {
            eprintln!("Host setup: {err}");
            Some(1)
        }
    }
}

#[cfg(not(target_os = "linux"))]
fn setup_host() -> hbb_common::ResultType<()> {
    hbb_common::bail!("Automatic host setup requires the Linux DEB installer")
}

#[cfg(target_os = "linux")]
fn setup_host() -> hbb_common::ResultType<()> {
    use base::config::keys;
    use hbb_common::{bail, config::Config};
    use std::{
        fs,
        io::Write,
        os::unix::fs::{DirBuilderExt, OpenOptionsExt, PermissionsExt},
    };

    if !crate::platform::is_root() || !crate::platform::is_installed() {
        bail!("Install the host package and run setup as root");
    }
    let profile: Profile =
        serde_json::from_str(option_env!("ECTRON_DEPLOYMENT_PROFILE").unwrap_or("{}"))
            .map_err(|_| hbb_common::anyhow::anyhow!("This is not a configured host build"))?;
    if profile.role != "host" || profile.password.is_empty() {
        bail!("This is not a configured host build");
    }
    let _scope = crate::ipc::UserMainIpcScope::new();
    let id = crate::ipc::get_config("id")?
        .filter(|id| !id.is_empty())
        .ok_or_else(|| hbb_common::anyhow::anyhow!("Waiting for the host service device ID"))?;
    crate::ipc::set_permanent_password(profile.password.clone())?;
    let required = [
        (keys::OPTION_VERIFICATION_METHOD, "use-permanent-password"),
        (keys::OPTION_APPROVE_MODE, "password"),
        (keys::OPTION_ALLOW_ONLY_CONN_WINDOW_OPEN, "N"),
        (keys::OPTION_ENABLE_KEYBOARD, "Y"),
    ];
    let mut options = crate::ipc::get_options();
    for (key, value) in required {
        options.insert(key.to_owned(), value.to_owned());
    }
    crate::ipc::set_options(options)?;
    let actual = crate::ipc::get_options();
    if required
        .iter()
        .any(|(key, value)| actual.get(*key).map(String::as_str) != Some(*value))
        || !crate::ipc::is_permanent_password_set()
    {
        bail!("The host service did not retain the unattended settings");
    }
    let directory = std::path::Path::new("/var/lib").join(crate::get_app_name().to_lowercase());
    fs::DirBuilder::new()
        .mode(0o700)
        .recursive(true)
        .create(&directory)?;
    fs::set_permissions(&directory, fs::Permissions::from_mode(0o700))?;
    let path = directory.join("host-connection.json");
    let mut file = fs::OpenOptions::new()
        .write(true)
        .create(true)
        .truncate(true)
        .mode(0o600)
        .custom_flags(hbb_common::libc::O_NOFOLLOW)
        .open(&path)?;
    file.set_permissions(fs::Permissions::from_mode(0o600))?;
    let connection = serde_json::json!({
        "brand": crate::get_app_name(), "id": id, "password": profile.password,
        "server": Config::get_option("custom-rendezvous-server"),
    });
    file.write_all(serde_json::to_string_pretty(&connection)?.as_bytes())?;
    file.sync_all()?;
    println!("Unattended host ready. Device ID: {id}");
    println!("Private connection profile: {}", path.display());
    Ok(())
}
