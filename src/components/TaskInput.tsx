/**
 * src/components/TaskInput.tsx — Multi-line task input with context file chips.
 *
 * React equivalent of TaskInput.qml.
 * Features:
 *   • Multi-line text input — send on Ctrl+Enter
 *   • Send button + file button stacked on the right side of the textarea
 *   • Context file chips shown above input
 */

import { useState, useRef, type KeyboardEvent } from "react";
import { useAgentStore } from "../store/agentStore";

interface TaskInputProps {
  onSendTask: (task: string) => void;
}

export default function TaskInput({ onSendTask }: TaskInputProps) {
  const [text, setText] = useState("");
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const contextFiles = useAgentStore((s) => s.contextFiles);
  const removeContextFile = useAgentStore((s) => s.removeContextFile);
  const setFileTreeOpen = useAgentStore((s) => s.setFileTreeOpen);

  const handleSend = () => {
    const trimmed = text.trim();
    if (!trimmed) return;
    onSendTask(trimmed);
    setText("");
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.key === "Enter" || e.key === "NumpadEnter") && e.ctrlKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div
      className="flex-shrink-0 border-t px-3 py-2 space-y-2"
      style={{
        borderColor: "var(--border-color, rgba(255,255,255,0.1))",
        backgroundColor: "var(--bg-header, #2a2e32)",
      }}
    >
      {/* Context file chips — above input */}
      {contextFiles.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {contextFiles.map((file) => (
            <span
              key={file}
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs"
              style={{
                backgroundColor: "rgba(61, 174, 233, 0.1)",
                border: "1px solid rgba(61, 174, 233, 0.3)",
                color: "#3DAEE9",
              }}
            >
              <span className="truncate max-w-[150px]">
                {file.split("/").pop() || file}
              </span>
              <button
                onClick={() => removeContextFile(file)}
                className="hover:opacity-70 flex-shrink-0"
                title={`Remove: ${file}`}
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </span>
          ))}
        </div>
      )}

      {/* Input row: text area + buttons stacked on right */}
      <div className="flex gap-2 items-end">
        <textarea
          ref={inputRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Describe your task... (Ctrl+Enter)"
          rows={2}
          className="flex-1 resize-none rounded-md px-3 py-2 text-sm outline-none transition-colors min-h-[2.5rem] max-h-[8rem]"
          style={{
            backgroundColor: "var(--bg-input, rgba(0,0,0,0.25))",
            border: "1px solid var(--border-color, rgba(255,255,255,0.1))",
            color: "var(--text-primary, #eff1f5)",
          }}
        />
        <div className="flex flex-col gap-1.5">
          <button
            onClick={handleSend}
            disabled={!text.trim()}
            className="p-2 rounded-md transition-colors disabled:opacity-30 hover:opacity-80"
            style={{
              backgroundColor: text.trim() ? "var(--accent-color, #3DAEE9)" : "rgba(255,255,255,0.05)",
              color: text.trim() ? "#fff" : "var(--text-disabled)",
              border: "1px solid var(--border-color, rgba(255,255,255,0.1))",
            }}
            title="Send (Ctrl+Enter)"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          </button>
          <button
            onClick={() => setFileTreeOpen(true)}
            className="p-2 rounded-md transition-colors hover:opacity-80"
            style={{
              color: "var(--text-secondary)",
              border: "1px solid var(--border-color, rgba(255,255,255,0.1))",
              backgroundColor: "rgba(255,255,255,0.03)",
            }}
            title="Attach Files"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
