#!/usr/bin/env python3
"""
A2A Hub Configurator — Simple GUI for managing agents.yaml and systemd services.

Features:
- View / add / edit / delete agents
- Set API keys, ports, capabilities, models
- Start / Stop / Restart Hub and agents
- Enable / disable systemd autostart
- Test agent connectivity

Usage:
    python configurator.py
"""

import json
import os
import subprocess
import sys
import yaml
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QFont, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

# ── Paths ────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
A2A_HUB_DIR = PROJECT_ROOT / "a2a_hub"
CONFIG_PATH = A2A_HUB_DIR / "config" / "agents.yaml"
SYSTEMD_HUB = f"a2a-hub@{os.environ.get('USER', 'neo')}.service"
SYSTEMD_AGENTS = f"a2a-agents@{os.environ.get('USER', 'neo')}.service"

# ── Helpers ──────────────────────────────────────────────────────────────────


def load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return yaml.safe_load(f) or {"hub": {}, "agents": [], "routing": {}}
    return {"hub": {}, "agents": [], "routing": {}}


def save_config(config: dict):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def systemctl(action: str, service: str) -> tuple[bool, str]:
    """Run systemctl command. Returns (success, output)."""
    try:
        result = subprocess.run(
            ["sudo", "systemctl", action, service],
            capture_output=True, text=True, timeout=15,
        )
        return result.returncode == 0, result.stdout + result.stderr
    except FileNotFoundError:
        # Try without sudo (if already root or polkit allows)
        try:
            result = subprocess.run(
                ["systemctl", action, service],
                capture_output=True, text=True, timeout=15,
            )
            return result.returncode == 0, result.stdout + result.stderr
        except Exception as e:
            return False, str(e)
    except Exception as e:
        return False, str(e)


def service_status(service: str) -> str:
    """Get simplified status: active, inactive, failed, not-found, unknown."""
    try:
        result = subprocess.run(
            ["systemctl", "is-active", service],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def service_enabled(service: str) -> bool:
    """Check if service is enabled for autostart."""
    try:
        result = subprocess.run(
            ["systemctl", "is-enabled", service],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() == "enabled"
    except Exception:
        return False


# ── Agent Dialog ─────────────────────────────────────────────────────────────


class AgentDialog(QDialog):
    """Dialog for adding or editing an agent."""

    def __init__(self, parent=None, agent: dict = None):
        super().__init__(parent)
        self.agent = agent or {}
        self.setWindowTitle("Edit Agent" if agent else "Add Agent")
        self.setMinimumWidth(500)
        self._build_ui()
        self._load_data()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        form = QFormLayout()

        self.name_edit = QLineEdit()
        form.addRow("Name:", self.name_edit)

        self.desc_edit = QLineEdit()
        form.addRow("Description:", self.desc_edit)

        self.role_combo = QComboBox()
        self.role_combo.addItems(["api", "local"])
        form.addRow("Role:", self.role_combo)

        self.endpoint_edit = QLineEdit()
        self.endpoint_edit.setPlaceholderText("http://127.0.0.1:8091")
        form.addRow("Endpoint:", self.endpoint_edit)

        self.port_spin = QSpinBox()
        self.port_spin.setRange(1024, 65535)
        self.port_spin.setValue(8091)
        form.addRow("Port:", self.port_spin)

        self.model_edit = QLineEdit()
        self.model_edit.setPlaceholderText("openrouter/owl-alpha")
        form.addRow("Model:", self.model_edit)

        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["openrouter", "llama.cpp", "ollama", "anthropic"])
        self.provider_combo.setEditable(True)
        form.addRow("Provider:", self.provider_combo)

        self.apikey_edit = QLineEdit()
        self.apikey_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.apikey_edit.setPlaceholderText("sk-or-v1-...")
        form.addRow("API Key:", self.apikey_edit)

        self.show_key_btn = QPushButton("👁 Show")
        self.show_key_btn.setCheckable(True)
        self.show_key_btn.toggled.connect(self._toggle_key_visibility)
        key_row = QHBoxLayout()
        key_row.addWidget(self.apikey_edit)
        key_row.addWidget(self.show_key_btn)
        form.addRow("", key_row)

        self.llama_host_edit = QLineEdit()
        self.llama_host_edit.setPlaceholderText("http://127.0.0.1:8085")
        form.addRow("llama.cpp Host:", self.llama_host_edit)

        self.cap_edit = QLineEdit()
        self.cap_edit.setPlaceholderText("code_analysis, debugging, search")
        form.addRow("Capabilities (comma-separated):", self.cap_edit)

        self.status_combo = QComboBox()
        self.status_combo.addItems(["active", "inactive"])
        form.addRow("Status:", self.status_combo)

        layout.addLayout(form)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _toggle_key_visibility(self, checked: bool):
        self.apikey_edit.setEchoMode(
            QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        )
        self.show_key_btn.setText("🙈 Hide" if checked else "👁 Show")

    def _load_data(self):
        if not self.agent:
            return
        self.name_edit.setText(self.agent.get("name", ""))
        self.desc_edit.setText(self.agent.get("description", ""))
        self.role_combo.setCurrentText(self.agent.get("role", "api"))
        endpoint = self.agent.get("endpoint", "")
        self.endpoint_edit.setText(endpoint)
        # Extract port from endpoint
        if ":" in endpoint:
            try:
                port = int(endpoint.rsplit(":", 1)[1])
                self.port_spin.setValue(port)
            except ValueError:
                pass
        self.model_edit.setText(self.agent.get("model", ""))
        self.provider_combo.setCurrentText(self.agent.get("provider", "openrouter"))
        self.apikey_edit.setText(self.agent.get("api_key", ""))
        self.llama_host_edit.setText(self.agent.get("llama_host", "http://127.0.0.1:8085"))
        caps = self.agent.get("capabilities", [])
        self.cap_edit.setText(", ".join(caps))
        self.status_combo.setCurrentText(self.agent.get("status", "active"))

    def get_agent(self) -> dict:
        port = self.port_spin.value()
        endpoint = self.endpoint_edit.text().strip()
        if not endpoint:
            endpoint = f"http://127.0.0.1:{port}"

        caps = [c.strip() for c in self.cap_edit.text().split(",") if c.strip()]

        agent = {
            "name": self.name_edit.text().strip(),
            "description": self.desc_edit.text().strip(),
            "role": self.role_combo.currentText(),
            "endpoint": endpoint,
            "agent_card_url": f"{endpoint}/.well-known/agent-card.json",
            "capabilities": caps,
            "auth_type": "none",
            "status": self.status_combo.currentText(),
        }

        model = self.model_edit.text().strip()
        if model:
            agent["model"] = model

        provider = self.provider_combo.currentText().strip()
        if provider:
            agent["provider"] = provider

        api_key = self.apikey_edit.text().strip()
        if api_key:
            agent["api_key"] = api_key

        llama_host = self.llama_host_edit.text().strip()
        if llama_host:
            agent["llama_host"] = llama_host

        return agent


# ── Main Window ──────────────────────────────────────────────────────────────


class MainWindow(QMainWindow):
    status_refresh_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.setWindowTitle("A2A Hub Configurator")
        self.setMinimumSize(900, 650)
        self._build_menu()
        self._build_toolbar()
        self._build_ui()
        self._refresh_agents()
        self._refresh_status()

        # Auto-refresh status every 5 seconds
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh_status)
        self.timer.start(5000)

    # ── Build UI ──────────────────────────────────────────────────────────

    def _build_menu(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("&File")

        reload_action = QAction("🔄 Reload Config", self)
        reload_action.triggered.connect(self._reload_config)
        file_menu.addAction(reload_action)

        save_action = QAction("💾 Save Config", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self._save_config)
        file_menu.addAction(save_action)

        file_menu.addSeparator()

        quit_action = QAction("❌ Quit", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        service_menu = menubar.addMenu("&Services")

        self.start_hub_action = QAction("▶ Start Hub", self)
        self.start_hub_action.triggered.connect(lambda: self._service_action("start", SYSTEMD_HUB))
        service_menu.addAction(self.start_hub_action)

        self.stop_hub_action = QAction("⏹ Stop Hub", self)
        self.stop_hub_action.triggered.connect(lambda: self._service_action("stop", SYSTEMD_HUB))
        service_menu.addAction(self.stop_hub_action)

        self.restart_hub_action = QAction("🔄 Restart Hub", self)
        self.restart_hub_action.triggered.connect(lambda: self._service_action("restart", SYSTEMD_HUB))
        service_menu.addAction(self.restart_hub_action)

        service_menu.addSeparator()

        self.start_agents_action = QAction("▶ Start Agents", self)
        self.start_agents_action.triggered.connect(lambda: self._service_action("start", SYSTEMD_AGENTS))
        service_menu.addAction(self.start_agents_action)

        self.stop_agents_action = QAction("⏹ Stop Agents", self)
        self.stop_agents_action.triggered.connect(lambda: self._service_action("stop", SYSTEMD_AGENTS))
        service_menu.addAction(self.stop_agents_action)

        self.restart_agents_action = QAction("🔄 Restart Agents", self)
        self.restart_agents_action.triggered.connect(lambda: self._service_action("restart", SYSTEMD_AGENTS))
        service_menu.addAction(self.restart_agents_action)

        service_menu.addSeparator()

        self.enable_autostart_action = QAction("✅ Enable Autostart", self)
        self.enable_autostart_action.triggered.connect(self._enable_autostart)
        service_menu.addAction(self.enable_autostart_action)

        self.disable_autostart_action = QAction("❌ Disable Autostart", self)
        self.disable_autostart_action.triggered.connect(self._disable_autostart)
        service_menu.addAction(self.disable_autostart_action)

        help_menu = menubar.addMenu("&Help")
        about_action = QAction("About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _build_toolbar(self):
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)

        toolbar.addAction("➕ Add Agent", self._add_agent)
        toolbar.addAction("✏️ Edit", self._edit_agent)
        toolbar.addAction("🗑 Delete", self._delete_agent)
        toolbar.addSeparator()
        toolbar.addAction("▶ Start All", self._start_all)
        toolbar.addAction("⏹ Stop All", self._stop_all)
        toolbar.addSeparator()
        toolbar.addAction("🔄 Refresh", self._refresh_status)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # ── Top: Service Status ──────────────────────────────────────────
        status_group = QGroupBox("Service Status")
        status_layout = QHBoxLayout(status_group)

        self.hub_status_label = QLabel("Hub: ⏳")
        self.hub_status_label.setFont(QFont("monospace", 12))
        status_layout.addWidget(self.hub_status_label)

        self.agents_status_label = QLabel("Agents: ⏳")
        self.agents_status_label.setFont(QFont("monospace", 12))
        status_layout.addWidget(self.agents_status_label)

        self.hub_autostart_label = QLabel("Hub Autostart: ⏳")
        self.hub_autostart_label.setFont(QFont("monospace", 10))
        status_layout.addWidget(self.hub_autostart_label)

        self.agents_autostart_label = QLabel("Agents Autostart: ⏳")
        self.agents_autostart_label.setFont(QFont("monospace", 10))
        status_layout.addWidget(self.agents_autostart_label)

        status_layout.addStretch()

        main_layout.addWidget(status_group)

        # ── Middle: Splitter (Agents table | Log) ────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Agents table
        agents_widget = QWidget()
        agents_layout = QVBoxLayout(agents_widget)
        agents_layout.setContentsMargins(0, 0, 0, 0)

        agents_header = QHBoxLayout()
        agents_header.addWidget(QLabel("<b>Agents</b>"))
        agents_header.addStretch()
        add_btn = QPushButton("➕ Add")
        add_btn.clicked.connect(self._add_agent)
        agents_header.addWidget(add_btn)
        edit_btn = QPushButton("✏️ Edit")
        edit_btn.clicked.connect(self._edit_agent)
        agents_header.addWidget(edit_btn)
        del_btn = QPushButton("🗑 Delete")
        del_btn.clicked.connect(self._delete_agent)
        agents_header.addWidget(del_btn)
        agents_layout.addLayout(agents_header)

        self.agents_table = QTableWidget()
        self.agents_table.setColumnCount(6)
        self.agents_table.setHorizontalHeaderLabels(["Name", "Role", "Endpoint", "Model", "Status", "Capabilities"])
        self.agents_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.agents_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.agents_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.agents_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.agents_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.agents_table.doubleClicked.connect(self._edit_agent)
        self.agents_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.agents_table.customContextMenuRequested.connect(self._agent_context_menu)
        agents_layout.addWidget(self.agents_table)

        splitter.addWidget(agents_widget)

        # Log output
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        log_layout.setContentsMargins(0, 0, 0, 0)
        log_layout.addWidget(QLabel("<b>Log</b>"))
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setFont(QFont("monospace", 9))
        log_layout.addWidget(self.log_output)

        splitter.addWidget(log_widget)
        splitter.setSizes([600, 300])

        main_layout.addWidget(splitter)

        # ── Bottom: Quick Actions ────────────────────────────────────────
        quick_group = QGroupBox("Quick Actions")
        quick_layout = QHBoxLayout(quick_group)

        quick_layout.addWidget(QLabel("Hub:"))
        quick_layout.addWidget(self._make_btn("Start", lambda: self._service_action("start", SYSTEMD_HUB)))
        quick_layout.addWidget(self._make_btn("Stop", lambda: self._service_action("stop", SYSTEMD_HUB)))
        quick_layout.addWidget(self._make_btn("Restart", lambda: self._service_action("restart", SYSTEMD_HUB)))
        quick_layout.addWidget(self._make_btn("Logs", self._show_hub_logs))

        quick_layout.addSpacing(20)

        quick_layout.addWidget(QLabel("Agents:"))
        quick_layout.addWidget(self._make_btn("Start", lambda: self._service_action("start", SYSTEMD_AGENTS)))
        quick_layout.addWidget(self._make_btn("Stop", lambda: self._service_action("stop", SYSTEMD_AGENTS)))
        quick_layout.addWidget(self._make_btn("Restart", lambda: self._service_action("restart", SYSTEMD_AGENTS)))
        quick_layout.addWidget(self._make_btn("Logs", self._show_agent_logs))

        quick_layout.addStretch()

        main_layout.addWidget(quick_group)

        # Status bar
        self.statusBar().showMessage(f"Config: {CONFIG_PATH}")

    def _make_btn(self, text: str, callback) -> QPushButton:
        btn = QPushButton(text)
        btn.clicked.connect(callback)
        return btn

    # ── Refresh ──────────────────────────────────────────────────────────

    def _refresh_agents(self):
        self.config = load_config()
        agents = self.config.get("agents", [])
        self.agents_table.setRowCount(len(agents))

        for i, agent in enumerate(agents):
            self.agents_table.setItem(i, 0, QTableWidgetItem(agent.get("name", "")))
            self.agents_table.setItem(i, 1, QTableWidgetItem(agent.get("role", "")))
            self.agents_table.setItem(i, 2, QTableWidgetItem(agent.get("endpoint", "")))
            self.agents_table.setItem(i, 3, QTableWidgetItem(agent.get("model", "")))

            status = agent.get("status", "unknown")
            status_item = QTableWidgetItem(status)
            if status == "active":
                status_item.setForeground(Qt.GlobalColor.darkGreen)
            else:
                status_item.setForeground(Qt.GlobalColor.red)
            self.agents_table.setItem(i, 4, status_item)

            caps = ", ".join(agent.get("capabilities", []))
            self.agents_table.setItem(i, 5, QTableWidgetItem(caps))

    def _refresh_status(self):
        # Hub status
        hub_st = service_status(SYSTEMD_HUB)
        hub_icon = {"active": "🟢", "inactive": "🔴", "failed": "💥"}.get(hub_st, "⚪")
        self.hub_status_label.setText(f"Hub: {hub_icon} {hub_st}")

        # Agents status
        agents_st = service_status(SYSTEMD_AGENTS)
        agents_icon = {"active": "🟢", "inactive": "🔴", "failed": "💥"}.get(agents_st, "⚪")
        self.agents_status_label.setText(f"Agents: {agents_icon} {agents_st}")

        # Autostart
        hub_en = service_enabled(SYSTEMD_HUB)
        self.hub_autostart_label.setText(f"Hub Autostart: {'✅' if hub_en else '❌'}")

        agents_en = service_enabled(SYSTEMD_AGENTS)
        self.agents_autostart_label.setText(f"Agents Autostart: {'✅' if agents_en else '❌'}")

    # ── Agent CRUD ───────────────────────────────────────────────────────

    def _add_agent(self):
        dialog = AgentDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            agent = dialog.get_agent()
            if not agent.get("name"):
                QMessageBox.warning(self, "Error", "Agent name is required")
                return
            self.config.setdefault("agents", []).append(agent)
            self._save_config()
            self._refresh_agents()
            self._log(f"Added agent: {agent['name']}")

    def _edit_agent(self):
        row = self.agents_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Info", "Select an agent to edit")
            return
        agents = self.config.get("agents", [])
        if row >= len(agents):
            return
        dialog = AgentDialog(self, agents[row])
        if dialog.exec() == QDialog.DialogCode.Accepted:
            agent = dialog.get_agent()
            if not agent.get("name"):
                QMessageBox.warning(self, "Error", "Agent name is required")
                return
            agents[row] = agent
            self._save_config()
            self._refresh_agents()
            self._log(f"Updated agent: {agent['name']}")

    def _delete_agent(self):
        row = self.agents_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Info", "Select an agent to delete")
            return
        agents = self.config.get("agents", [])
        if row >= len(agents):
            return
        name = agents[row].get("name", "unknown")
        reply = QMessageBox.question(
            self, "Confirm", f"Delete agent '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            agents.pop(row)
            self._save_config()
            self._refresh_agents()
            self._log(f"Deleted agent: {name}")

    def _agent_context_menu(self, pos):
        row = self.agents_table.currentRow()
        if row < 0:
            return
        menu = QMenu(self)
        menu.addAction("✏️ Edit", self._edit_agent)
        menu.addAction("🗑 Delete", self._delete_agent)
        menu.addSeparator()
        menu.addAction("📋 Copy Endpoint", self._copy_endpoint)
        menu.exec(self.agents_table.viewport().mapToGlobal(pos))

    def _copy_endpoint(self):
        row = self.agents_table.currentRow()
        if row < 0:
            return
        endpoint = self.agents_table.item(row, 2)
        if endpoint:
            QApplication.clipboard().setText(endpoint.text())
            self._log(f"Copied: {endpoint.text()}")

    # ── Services ─────────────────────────────────────────────────────────

    def _service_action(self, action: str, service: str):
        self._log(f"Running: systemctl {action} {service}...")
        success, output = systemctl(action, service)
        if success:
            self._log(f"✅ {action} {service}: OK")
        else:
            self._log(f"❌ {action} {service}: {output.strip() or 'failed'}")
        self._refresh_status()

    def _start_all(self):
        self._service_action("start", SYSTEMD_HUB)
        self._service_action("start", SYSTEMD_AGENTS)

    def _stop_all(self):
        self._service_action("stop", SYSTEMD_AGENTS)
        self._service_action("stop", SYSTEMD_HUB)

    def _enable_autostart(self):
        self._service_action("enable", SYSTEMD_HUB)
        self._service_action("enable", SYSTEMD_AGENTS)

    def _disable_autostart(self):
        self._service_action("disable", SYSTEMD_AGENTS)
        self._service_action("disable", SYSTEMD_HUB)

    def _show_hub_logs(self):
        try:
            result = subprocess.run(
                ["journalctl", "-u", SYSTEMD_HUB, "-n", "50", "--no-pager"],
                capture_output=True, text=True, timeout=10,
            )
            self._log(f"── Hub Logs ──\n{result.stdout}")
        except Exception as e:
            self._log(f"Error reading hub logs: {e}")

    def _show_agent_logs(self):
        try:
            result = subprocess.run(
                ["journalctl", "-u", SYSTEMD_AGENTS, "-n", "50", "--no-pager"],
                capture_output=True, text=True, timeout=10,
            )
            self._log(f"── Agent Logs ──\n{result.stdout}")
        except Exception as e:
            self._log(f"Error reading agent logs: {e}")

    # ── Config ───────────────────────────────────────────────────────────

    def _reload_config(self):
        self.config = load_config()
        self._refresh_agents()
        self._log("Config reloaded")

    def _save_config(self):
        save_config(self.config)
        self._log(f"Config saved to {CONFIG_PATH}")

    # ── Misc ─────────────────────────────────────────────────────────────

    def _log(self, message: str):
        from datetime import datetime
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_output.append(f"[{ts}] {message}")

    def _show_about(self):
        QMessageBox.about(
            self, "About A2A Hub Configurator",
            "<h3>A2A Hub Configurator</h3>"
            "<p>Simple GUI for managing A2A Hub agents and services.</p>"
            "<p>Features:</p>"
            "<ul>"
            "<li>View / add / edit / delete agents</li>"
            "<li>Manage API keys, ports, capabilities</li>"
            "<li>Start / Stop / Restart Hub and agents</li>"
            "<li>Enable / disable systemd autostart</li>"
            "<li>View service logs</li>"
            "</ul>"
        )


# ── Entry Point ──────────────────────────────────────────────────────────────


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("A2A Hub Configurator")

    # Simple dark-ish style
    app.setStyleSheet("""
        QMainWindow { background: #2b2b2b; }
        QWidget { color: #eeeeee; background: #2b2b2b; }
        QTableWidget { background: #333333; color: #eeeeee; gridline-color: #555555; }
        QTableWidget::item:selected { background: #4a6fa5; }
        QTextEdit { background: #1e1e1e; color: #d4d4d4; }
        QLineEdit { background: #3c3c3c; color: #eeeeee; border: 1px solid #555555; padding: 2px; }
        QPushButton { background: #4a4a4a; border: 1px solid #666666; padding: 4px 12px; }
        QPushButton:hover { background: #5a5a5a; }
        QPushButton:pressed { background: #3a3a3a; }
        QGroupBox { border: 1px solid #555555; margin-top: 8px; padding-top: 16px; }
        QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; }
        QMenuBar { background: #333333; color: #eeeeee; }
        QMenuBar::item:selected { background: #4a6fa5; }
        QMenu { background: #333333; color: #eeeeee; }
        QMenu::item:selected { background: #4a6fa5; }
        QStatusBar { background: #333333; }
        QToolBar { background: #383838; border-bottom: 1px solid #555555; }
        QComboBox { background: #3c3c3c; color: #eeeeee; border: 1px solid #555555; }
        QSpinBox { background: #3c3c3c; color: #eeeeee; border: 1px solid #555555; }
        QCheckBox { color: #eeeeee; }
        QLabel { color: #eeeeee; }
    """)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
