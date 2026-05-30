/**
 * src/types.ts — Core type definitions for AI Agent Panel.
 *
 * Mirrors the QML message/agent types used in SidePanelWindow.qml.
 */

// ── Agent status ──
export type AgentStatus =
  | "idle"
  | "thinking"
  | "executing"
  | "waiting_user"
  | "complete"
  | "error";

// ── Message types (color-coded, matching QML ChatView) ──
export type MessageType =
  | "user"          // user messages (right-aligned bubble)
  | "agent"         // agent text responses (left-aligned bubble)
  | "thought"       // default text color
  | "tool_call"     // amber #EF9F27
  | "tool_result"   // teal #1D9E75
  | "error"         // red #E24B4A
  | "task_complete" // green #639922
  | "question";     // blue #3DAEE9

// ── Chat message ──
export interface ChatMessage {
  id: string;
  type: MessageType;
  content: string;
  toolName?: string;
  options?: string[];
  iteration?: string;
  streaming?: boolean;
  success?: boolean;
  timestamp: number;
}

// ── File tree entry ──
export interface FileEntry {
  name: string;
  path: string;
  isDir: boolean;
  isLink: boolean;
  size: number;
  mtime: number;
  checked: boolean;
}

// ── Agent state (Zustand store shape) ──
export interface AgentState {
  connected: boolean;
  status: AgentStatus;
  messages: ChatMessage[];
  contextFiles: string[];
  currentDir: string;
  workingDir: string;
  fileEntries: FileEntry[];
  selectedFiles: string[];
  filterText: string;
  history: string[];
  loadingFiles: boolean;
  fileTreeOpen: boolean;
  panelVisible: boolean;

  setConnected: (v: boolean) => void;
  setStatus: (s: AgentStatus) => void;
  addMessage: (msg: Omit<ChatMessage, "id" | "timestamp">) => void;
  appendToken: (content: string, msgType: MessageType) => void;
  setMessages: (msgs: ChatMessage[]) => void;
  clearMessages: () => void;
  addContextFile: (path: string) => void;
  removeContextFile: (path: string) => void;
  setFileEntries: (entries: FileEntry[]) => void;
  setCurrentDir: (dir: string) => void;
  setFilterText: (text: string) => void;
  toggleFileSelection: (path: string) => void;
  navigateTo: (path: string) => void;
  goBack: () => void;
  setFileTreeOpen: (open: boolean) => void;
  setLoadingFiles: (loading: boolean) => void;
  setPanelVisible: (visible: boolean) => void;
  togglePanel: () => void;
}
