/**
 * src-tauri/src/commands.rs — Tauri commands for AI Agent D-Bus bridge.
 *
 * Each command spawns a Python subprocess (dbus_helper.py) to communicate
 * with the org.kde.aiagent D-Bus service. This avoids linking dbus-python
 * into the Rust binary while reusing the existing Python D-Bus infrastructure.
 *
 * Signal listening is handled separately by spawn_dbus_listener() in lib.rs,
 * which runs dbus_listener.py as a long-lived subprocess and forwards
 * D-Bus signals to the React frontend via Tauri events.
 */

use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use std::sync::Mutex;
use tauri::State;

// Keep greet for backward compatibility
#[tauri::command]
pub fn greet(name: &str) -> String {
    format!("Hello, {}!", name)
}

// ── Shared state: handle to the running agent task ──
pub struct AgentState {
    /// Path to the Python virtual environment or system python
    pub python_path: Mutex<String>,
    /// Path to the agent directory containing dbus_helper.py / dbus_listener.py
    pub agent_dir: Mutex<String>,
}

impl AgentState {
    pub fn new() -> Self {
        Self {
            python_path: Mutex::new("python3".to_string()),
            // Agent service runs from ~/.local/share/kde-ai-agent/agent/ (systemd)
            agent_dir: Mutex::new(
                dirs::home_dir()
                    .map(|d| d.join(".local/share/kde-ai-agent/agent"))
                    .and_then(|p| p.to_str().map(String::from))
                    .unwrap_or_else(|| "/home/neo/.local/share/kde-ai-agent/agent".to_string()),
            ),
        }
    }
}

// ── Response types ──

#[derive(Debug, Serialize, Deserialize)]
pub struct AgentStatusResponse {
    pub status: String,
    #[serde(default)]
    pub connected: bool,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct CommandResponse {
    pub success: bool,
    pub message: String,
}

// ── Helper: spawn dbus_helper.py and capture output ──
async fn call_dbus_helper(
    agent_state: &State<'_, AgentState>,
    args: Vec<String>,
) -> Result<String, String> {
    let agent_dir = agent_state.agent_dir.lock().unwrap().clone();
    let python = agent_state.python_path.lock().unwrap().clone();

    let helper_path = PathBuf::from(&agent_dir).join("dbus_helper.py");
    if !helper_path.exists() {
        return Err(format!("dbus_helper.py not found at {:?}", helper_path));
    }

    let output = tokio::process::Command::new(&python)
        .arg(&helper_path)
        .args(&args)
        .output()
        .await
        .map_err(|e| format!("Failed to spawn dbus_helper.py: {}", e))?;

    let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();

    if !output.status.success() {
        return Err(format!(
            "dbus_helper.py exited with code {:?}: {}",
            output.status.code(),
            stderr
        ));
    }

    if stderr.is_empty() {
        Ok(stdout)
    } else {
        Ok(format!("{}\n{}", stdout, stderr))
    }
}

// ════════════════════════════════════════════════════════════
// Tauri Commands
// ════════════════════════════════════════════════════════════

/// Get current agent status from D-Bus.
/// Calls: python3 dbus_helper.py get_status
#[tauri::command]
pub async fn get_agent_status(
    agent_state: State<'_, AgentState>,
) -> Result<AgentStatusResponse, String> {
    let output = call_dbus_helper(&agent_state, vec!["get_status".to_string()]).await?;

    // Parse "STATUS: {json}" format from dbus_helper.py
    let json_str = if output.starts_with("STATUS:") {
        output.trim_start_matches("STATUS:").trim()
    } else if output.starts_with("ERROR:") {
        return Err(output.trim_start_matches("ERROR:").trim().to_string());
    } else {
        &output
    };

    // Try to parse as JSON, fallback to simple status string
    match serde_json::from_str::<serde_json::Value>(json_str) {
        Ok(val) => {
            let status = val
                .get("status")
                .and_then(|v| v.as_str())
                .unwrap_or("unknown")
                .to_string();
            Ok(AgentStatusResponse {
                status,
                connected: true,
            })
        }
        Err(_) => {
            // Fallback: treat the whole string as status
            Ok(AgentStatusResponse {
                status: json_str.to_string(),
                connected: true,
            })
        }
    }
}

/// Run a task on the agent via D-Bus.
/// Calls: python3 dbus_helper.py run_task "task string" '["file1", "file2"]'
#[tauri::command]
pub async fn run_task(
    agent_state: State<'_, AgentState>,
    task: String,
    file_context: Vec<String>,
) -> Result<CommandResponse, String> {
    let files_json = serde_json::to_string(&file_context)
        .map_err(|e| format!("Failed to serialize file_context: {}", e))?;

    let output = call_dbus_helper(
        &agent_state,
        vec![
            "run_task".to_string(),
            task,
            files_json,
        ],
    )
    .await?;

    if output.starts_with("OK:") {
        Ok(CommandResponse {
            success: true,
            message: output.trim_start_matches("OK:").trim().to_string(),
        })
    } else if output.starts_with("ERROR:") {
        Ok(CommandResponse {
            success: false,
            message: output.trim_start_matches("ERROR:").trim().to_string(),
        })
    } else {
        Ok(CommandResponse {
            success: true,
            message: output,
        })
    }
}

/// Stop the currently running task via D-Bus.
/// Calls: python3 dbus_helper.py stop_task
#[tauri::command]
pub async fn stop_task(
    agent_state: State<'_, AgentState>,
) -> Result<CommandResponse, String> {
    let output = call_dbus_helper(&agent_state, vec!["stop_task".to_string()]).await?;

    if output.starts_with("OK:") {
        Ok(CommandResponse {
            success: true,
            message: output.trim_start_matches("OK:").trim().to_string(),
        })
    } else if output.starts_with("ERROR:") {
        Ok(CommandResponse {
            success: false,
            message: output.trim_start_matches("ERROR:").trim().to_string(),
        })
    } else {
        Ok(CommandResponse {
            success: true,
            message: output,
        })
    }
}

/// Provide user response to an ask_user question via D-Bus.
/// Calls: python3 dbus_helper.py provide_response "response text"
#[tauri::command]
pub async fn provide_response(
    agent_state: State<'_, AgentState>,
    response: String,
) -> Result<CommandResponse, String> {
    let output = call_dbus_helper(
        &agent_state,
        vec!["provide_response".to_string(), response],
    )
    .await?;

    if output.starts_with("OK:") {
        Ok(CommandResponse {
            success: true,
            message: output.trim_start_matches("OK:").trim().to_string(),
        })
    } else if output.starts_with("ERROR:") {
        Ok(CommandResponse {
            success: false,
            message: output.trim_start_matches("ERROR:").trim().to_string(),
        })
    } else {
        Ok(CommandResponse {
            success: true,
            message: output,
        })
    }
}

/// Check if the D-Bus agent service is available.
#[tauri::command]
pub async fn check_agent_connected(
    agent_state: State<'_, AgentState>,
) -> Result<bool, String> {
    match call_dbus_helper(&agent_state, vec!["get_status".to_string()]).await {
        Ok(output) => {
            if output.starts_with("ERROR:") {
                Ok(false)
            } else {
                Ok(true)
            }
        }
        Err(_) => Ok(false),
    }
}

/// Kill all stale dbus_listener.py processes.
/// Called on Tauri startup to prevent accumulation from previous runs.
#[tauri::command]
pub async fn cleanup_stale_listeners() -> Result<CommandResponse, String> {
    let output = tokio::process::Command::new("pkill")
        .args(["-f", "dbus_listener.py"])
        .output()
        .await
        .map_err(|e| format!("Failed to run pkill: {}", e))?;

    // pkill returns 0 if it killed something, 1 if nothing matched — both are OK
    let killed = output.status.code().unwrap_or(1) == 0;
    Ok(CommandResponse {
        success: true,
        message: if killed {
            "Cleaned up stale dbus_listener.py processes".to_string()
        } else {
            "No stale dbus_listener.py processes found".to_string()
        },
    })
}
