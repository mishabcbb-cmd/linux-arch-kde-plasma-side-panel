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
use tauri::Manager;
use tauri::Listener;
use tauri_plugin_global_shortcut::GlobalShortcutExt;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    env_logger::init();

    // ── NVIDIA + Wayland workaround ──────────────────
    // Auto-detect NVIDIA GPU on Wayland and apply env vars before
    // WebKitGTK initializes. Must be done before tauri::Builder.
    // See: docs/tauri-nvidia-wayland-research.md
    #[cfg(target_os = "linux")]
    {
        let is_wayland = std::env::var("XDG_SESSION_TYPE")
            .map(|s| s == "wayland")
            .unwrap_or(false)
            || std::env::var("WAYLAND_DISPLAY").is_ok();
        let has_nvidia = std::path::Path::new("/proc/driver/nvidia/version").exists();

        if is_wayland && has_nvidia {
            if std::env::var_os("__NV_DISABLE_EXPLICIT_SYNC").is_none() {
                std::env::set_var("__NV_DISABLE_EXPLICIT_SYNC", "1");
                log::info!("NVIDIA + Wayland: set __NV_DISABLE_EXPLICIT_SYNC=1");
            }
            if std::env::var_os("GSK_RENDERER").is_none() {
                std::env::set_var("GSK_RENDERER", "ngl");
                log::info!("NVIDIA + Wayland: set GSK_RENDERER=ngl");
            }
            if std::env::var_os("NVD_BACKEND").is_none() {
                std::env::set_var("NVD_BACKEND", "direct");
                log::info!("NVIDIA + Wayland: set NVD_BACKEND=direct");
            }
        }
    }

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
            commands::slide_panel,
            commands::toggle_panel_slide,
            commands::position_panel_left,
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
            let agent_dir = dirs::home_dir()
                .map(|d| d.join(".local/share/kde-ai-agent/agent"))
                .and_then(|p| p.to_str().map(String::from))
                .unwrap_or_else(|| {
                    "/home/neo/.local/share/kde-ai-agent/agent".to_string()
                });

            dbus_listener::spawn_dbus_listener(app_handle.clone(), agent_dir);
            log::info!("D-Bus signal listener (Python subprocess) started");

            // ── 2. Position window on left edge after window is created ──
            let app_handle_clone = app.handle().clone();
            app.listen("tauri://window-created", move |_| {
                log::info!("Window created event received");
                let app_handle_inner = app_handle_clone.clone();
                tauri::async_runtime::spawn(async move {
                    // Small delay to let the window fully initialize
                    tokio::time::sleep(std::time::Duration::from_millis(500)).await;
                    let _ = commands::position_panel_left().await;
                });
            });

            // ── 3. Register Super+A global shortcut for toggle ──
            {
                app.handle()
                    .global_shortcut()
                    .on_shortcut("Super+A", move |app, _shortcut, _event| {
                        log::info!("Super+A pressed!");
                        tauri::async_runtime::spawn(async move {
                            let _ = commands::toggle_panel_slide().await;
                        });
                    })
                    .map_err(|e| {
                        log::error!("Failed to register Super+A shortcut: {}", e);
                        e
                    })?;
                log::info!("Global shortcut Super+A registered");
            }

            // ── 4. LayerShell disabled ──
            log::info!("LayerShell: disabled for initial Wayland test");

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
