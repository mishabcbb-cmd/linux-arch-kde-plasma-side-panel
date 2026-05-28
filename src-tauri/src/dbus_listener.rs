/**
 * src-tauri/src/dbus_listener.rs — D-Bus signal listener via Python subprocess.
 *
 * Spawns dbus_listener.py as a long-lived subprocess, reads JSON lines from
 * its stdout, and emits them as Tauri events to the React frontend.
 *
 * This is the recommended approach for zbus v5 because:
 *   - zbus v5 Connection has no receive_message() method
 *   - SignalStream types are per-signal and can't be easily unified
 *   - Python dbus-python has mature, stable D-Bus signal handling
 *
 * The subprocess approach is reliable and matches the original QML design.
 */

use std::process::Stdio;
use tauri::Emitter;
use tauri::async_runtime::spawn;

/// Spawn the dbus_listener.py subprocess and forward D-Bus signals as Tauri events.
pub fn spawn_dbus_listener(app_handle: tauri::AppHandle, agent_dir: String) {
    spawn(async move {
        let listener_path = std::path::PathBuf::from(&agent_dir).join("dbus_listener.py");
        if !listener_path.exists() {
            log::error!("dbus_listener.py not found at {:?}", listener_path);
            let _ = app_handle.emit("dbus-signal", serde_json::json!({
                "signal": "ErrorOccurred",
                "error": format!("dbus_listener.py not found at {:?}", listener_path),
            }));
            return;
        }

        log::info!("Starting D-Bus signal listener: {:?}", listener_path);

        let mut child = match tokio::process::Command::new("python3")
            .arg(&listener_path)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
        {
            Ok(child) => child,
            Err(e) => {
                log::error!("Failed to spawn dbus_listener.py: {}", e);
                let _ = app_handle.emit("dbus-signal", serde_json::json!({
                    "signal": "ErrorOccurred",
                    "error": format!("Failed to spawn dbus_listener.py: {}", e),
                }));
                return;
            }
        };

        let stdout = match child.stdout.take() {
            Some(stdout) => stdout,
            None => {
                log::error!("Failed to capture stdout from dbus_listener.py");
                return;
            }
        };

        let reader = tokio::io::BufReader::new(stdout);
        let mut lines = tokio::io::AsyncBufReadExt::lines(reader);

        while let Ok(Some(line)) = lines.next_line().await {
            let trimmed = line.trim();
            if trimmed.is_empty() {
                continue;
            }

            match serde_json::from_str::<serde_json::Value>(trimmed) {
                Ok(json_val) => {
                    log::debug!("D-Bus signal: {}", trimmed);
                    if let Err(e) = app_handle.emit("dbus-signal", json_val) {
                        log::warn!("Failed to emit dbus-signal event: {}", e);
                    }
                }
                Err(e) => {
                    log::warn!("Failed to parse dbus_listener output: {} | line: {}", e, trimmed);
                }
            }
        }

        log::warn!("dbus_listener.py subprocess exited");
        let _ = app_handle.emit("dbus-signal", serde_json::json!({
            "signal": "_listener_stopped",
            "error": "dbus_listener.py subprocess exited",
        }));

        let _ = child.kill().await;
    });
}
