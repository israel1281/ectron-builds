pub(crate) fn setup() -> hbb_common::ResultType<()> {
    use base::config::keys;
    use hbb_common::{bail, config::Config};
    use std::{fs, io::Write, os::windows::fs::MetadataExt, path::PathBuf, process::Command, thread, time::Duration};

    #[derive(serde_derive::Deserialize)]
    struct Profile {
        role: String,
        password: String,
    }

    if !(super::is_root() || super::is_elevated(None)?) || !super::is_installed() {
        bail!("Install the host MSI and run setup with administrative privileges");
    }
    let profile: Profile =
        serde_json::from_str(option_env!("ECTRON_DEPLOYMENT_PROFILE").unwrap_or("{}"))
            .map_err(|_| hbb_common::anyhow::anyhow!("This is not a configured host build"))?;
    if profile.role != "host" || profile.password.is_empty() {
        bail!("This is not a configured host build");
    }
    let mut id = None;
    // The MSI starts the service before its IPC endpoint becomes ready.
    for attempt in 0..20 {
        if let Ok(Some(value)) = crate::ipc::get_config("id") {
            if !value.is_empty() {
                id = Some(value);
                break;
            }
        }
        if attempt < 19 {
            thread::sleep(Duration::from_secs(2));
        }
    }
    let id = id.ok_or_else(|| hbb_common::anyhow::anyhow!("The host service did not become ready"))?;
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
    if required.iter().any(|(key, value)| actual.get(*key).map(String::as_str) != Some(*value))
        || !crate::ipc::is_permanent_password_set()
    {
        bail!("The host service did not retain the unattended settings");
    }
    let directory = PathBuf::from(std::env::var_os("ProgramData")
        .ok_or_else(|| hbb_common::anyhow::anyhow!("ProgramData is unavailable"))?)
        .join(crate::get_app_name().to_lowercase()).join("host");
    fs::create_dir_all(&directory)?;
    if fs::symlink_metadata(&directory)?.file_attributes() & 0x400 != 0 {
        bail!("The private host connection directory cannot be a reparse point");
    }
    if !Command::new("icacls.exe").arg(&directory).arg("/reset").output()?.status.success() {
        bail!("Could not reset the private host connection directory permissions");
    }
    let status = Command::new("icacls.exe")
        .arg(&directory)
        .args(["/inheritance:r", "/grant:r", "*S-1-5-18:(OI)(CI)F", "*S-1-5-32-544:(OI)(CI)F"])
        .output()?.status;
    if !status.success() {
        bail!("Could not restrict the private host connection directory");
    }
    let path = directory.join("host-connection.json");
    if let Ok(metadata) = fs::symlink_metadata(&path) {
        if metadata.file_attributes() & 0x400 != 0 {
            bail!("The private host connection profile cannot be a reparse point");
        }
    }
    let mut file = fs::OpenOptions::new().write(true).create(true).open(&path)?;
    if !Command::new("icacls.exe").arg(&path).arg("/reset").output()?.status.success() {
        bail!("Could not restrict the private host connection profile permissions");
    }
    file.set_len(0)?;
    let connection = serde_json::json!({
        "brand": crate::get_app_name(), "id": id, "password": profile.password,
        "server": Config::get_option("custom-rendezvous-server"),
        "device_key": Config::get_key_pair().1.iter().map(|byte| format!("{byte:02x}")).collect::<String>(),
    });
    file.write_all(serde_json::to_string_pretty(&connection)?.as_bytes())?;
    file.sync_all()?;
    println!("Unattended host ready. Device ID: {id}");
    println!("Private connection profile: {}", path.display());
    Ok(())
}
