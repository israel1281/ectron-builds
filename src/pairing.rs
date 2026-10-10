pub(crate) fn start() {
    use hbb_common::{config::Config, log, tokio};
    use std::time::Duration;

    #[derive(serde_derive::Deserialize)]
    struct Profile {
        role: String,
        pairing_url: String,
        pairing_token: String,
    }
    let Ok(profile) = serde_json::from_str::<Profile>(
        option_env!("ECTRON_DEPLOYMENT_PROFILE").unwrap_or("{}"),
    ) else {
        return;
    };
    if profile.role != "host" || profile.pairing_url.is_empty() || profile.pairing_token.is_empty()
        || !crate::is_server() || !crate::platform::is_installed()
    {
        return;
    }
    let client = match reqwest::Client::builder()
        .use_rustls_tls()
        .https_only(true)
        .redirect(reqwest::redirect::Policy::none())
        .timeout(Duration::from_secs(10))
        .build()
    {
        Ok(client) => client,
        Err(_) => {
            log::error!("Could not initialize automatic host pairing");
            return;
        }
    };
    tokio::spawn(async move {
        loop {
            if Config::get_key_confirmed() && Config::get_option("stop-service") != "Y"
                && Config::get_option("verification-method") == "use-permanent-password"
                && Config::get_option("approve-mode") == "password"
            {
                let public_key = Config::get_key_pair().1;
                let device_key: String = public_key.iter().map(|byte| format!("{byte:02x}")).collect();
                let body = serde_json::json!({
                    "device_key": device_key, "id": Config::get_id(),
                    "name": crate::common::hostname(), "platform": std::env::consts::OS,
                });
                let result = client.post(format!("{}/v1/hosts", profile.pairing_url))
                    .bearer_auth(&profile.pairing_token).json(&body).send().await;
                if !matches!(result, Ok(response) if response.status().is_success()) {
                    hbb_common::throttled_log!(Duration::from_secs(300), warn, "Automatic host pairing is unavailable; retrying");
                }
            }
            tokio::time::sleep(Duration::from_secs(60)).await;
        }
    });
}
