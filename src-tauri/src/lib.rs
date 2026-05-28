/**
 * src-tauri/src/lib.rs — Tauri application entry point.
 *
 * Architecture:
 *   React ←→ invoke("command") ←→ Rust ←→ Python dbus_helper.py ←→ D-Bus
 *   React ←→ listen("dbus-signal") ←── Rust ←── Python dbus_listener.py ←── D-Bus signals
 *
 * LayerShell: Not implemented (Tauri 2 uses gtk v0.18, gtk4-layer-shell requires gtk4::Window).
 * Recommendation: Use KWin/Plasma native panel integration or wayland-client crate directly.
 */

mod commands;
mod dbus_listener;
#[allow(dead_code)]
mod layer_shell;

use commands::AgentState;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    env_logger::init();

    let agent_state = AgentState::new();

    tauri::Builder::default()
        .manage(agent_state)
        .invoke_handler(tauri::generate_handler![
            commands::greet,
            commands::get_agent_status,
            commands::run_task,
            commands::stop_task,
            commands::provide_response,
            commands::check_agent_connected,
            commands::cleanup_stale_listeners,
        ])
        .plugin(tauri_plugin_store::Builder::default().build())
        .plugin(tauri_plugin_autostart::init(
            tauri_plugin_autostart::MacosLauncher::LaunchAgent,
            None,
        ))
        .plugin(tauri_plugin_global_shortcut::Builder::default().build())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_single_instance::init(|app, _, _| {
            let _ = app;
        }))
        .setup(|app| {
            let app_handle = app.handle().clone();

            // ── 0. Clean up stale dbus_listener.py from previous runs ──
            log::info!("Cleaning up stale dbus_listener.py processes...");
            let _ = std::process::Command::new("pkill")
                .args(["-f", "dbus_listener.py"])
                .output();

            // ── 1. Start D-Bus signal listener (Python subprocess) ──
            // Agent service runs from ~/.local/share/kde-ai-agent/agent/ (systemd)
            let agent_dir = dirs::home_dir()
                .map(|d| d.join(".local/share/kde-ai-agent/agent"))
                .and_then(|p| p.to_str().map(String::from))
                .unwrap_or_else(|| {
                    "/home/neo/.local/share/kde-ai-agent/agent".to_string()
                });

            dbus_listener::spawn_dbus_listener(app_handle.clone(), agent_dir);
            log::info!("D-Bus signal listener (Python subprocess) started");

            // ── 2. LayerShell disabled for initial Wayland test ──
            // LayerShell requires a separate Wayland connection which conflicts
            // with Tauri's GTK Wayland backend. Re-enable after investigating
            // gtk4-layer-shell integration or KWin native panel protocol.
            log::info!("LayerShell: disabled for initial Wayland test");

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
