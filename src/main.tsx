/**
 * src/main.tsx — Entry point for AI Agent Panel React frontend.
 *
 * Bootstrapped by Tauri's WebView (tauri.conf.json → frontendDist: "../dist").
 * Replaces the QML entry point (main.qml → SidePanelWindow.qml).
 */

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
