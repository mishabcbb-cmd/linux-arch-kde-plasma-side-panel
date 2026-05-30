/**
 * src/store/agentStore.ts — Zustand store for AI Agent Panel.
 *
 * Central state management replacing QML's property system in SidePanelWindow.qml.
 * Handles: agent connection, chat messages, file tree, context files.
 */

import { create } from "zustand";
import type { AgentState, ChatMessage } from "../types";

let messageIdCounter = 0;
function nextId(): string {
  return `msg-${++messageIdCounter}-${Date.now()}`;
}

export const useAgentStore = create<AgentState>((set) => ({
  // ── Initial state ──
  connected: false,
  status: "idle",
  messages: [],
  contextFiles: [],
  currentDir: "~",
  workingDir: "~",
  fileEntries: [],
  selectedFiles: [],
  filterText: "",
  history: [],
  loadingFiles: false,
  fileTreeOpen: false,
  panelVisible: true,

  // ── Connection ──
  setConnected: (v) => set({ connected: v }),
  setStatus: (s) => set({ status: s }),

  // ── Chat messages ──
  addMessage: (msg) =>
    set((state) => ({
      messages: [
        ...state.messages,
        {
          ...msg,
          id: nextId(),
          timestamp: Date.now(),
        } as ChatMessage,
      ],
    })),

  appendToken: (content, msgType) =>
    set((state) => {
      const msgs = [...state.messages];
      const last = msgs.length > 0 ? msgs[msgs.length - 1] : null;
      if (last && last.type === msgType && last.streaming) {
        last.content += content;
      } else {
        msgs.push({
          id: nextId(),
          type: msgType,
          content,
          streaming: true,
          timestamp: Date.now(),
        });
      }
      return { messages: msgs };
    }),

  setMessages: (msgs) => set({ messages: msgs }),

  clearMessages: () => set({ messages: [] }),

  // ── Context files ──
  addContextFile: (path) =>
    set((state) => {
      if (state.contextFiles.includes(path)) return state;
      return { contextFiles: [...state.contextFiles, path] };
    }),

  removeContextFile: (path) =>
    set((state) => ({
      contextFiles: state.contextFiles.filter((f) => f !== path),
    })),

  // ── File tree ──
  setFileEntries: (entries) => set({ fileEntries: entries }),
  setCurrentDir: (dir) => set({ currentDir: dir }),
  setFilterText: (text) => set({ filterText: text }),
  setLoadingFiles: (loading) => set({ loadingFiles: loading }),

  toggleFileSelection: (path) =>
    set((state) => {
      const idx = state.selectedFiles.indexOf(path);
      if (idx >= 0) {
        return { selectedFiles: state.selectedFiles.filter((f) => f !== path) };
      }
      return { selectedFiles: [...state.selectedFiles, path] };
    }),

  navigateTo: (path) =>
    set((state) => ({
      history: [...state.history, state.currentDir],
      currentDir: path,
    })),

  goBack: () =>
    set((state) => {
      if (state.history.length === 0) return state;
      const prev = state.history[state.history.length - 1];
      return {
        currentDir: prev,
        history: state.history.slice(0, -1),
      };
    }),

  // ── UI ──
  setFileTreeOpen: (open) => set({ fileTreeOpen: open }),
  setPanelVisible: (visible) => set({ panelVisible: visible }),
  togglePanel: () => set((state) => ({ panelVisible: !state.panelVisible })),
}));
