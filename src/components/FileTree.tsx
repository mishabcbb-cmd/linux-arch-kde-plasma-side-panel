/**
 * src/components/FileTree.tsx — File browser with directory tree.
 *
 * React equivalent of FileTree.qml.
 * Features:
 *   • Directory tree navigation (click to enter, back button)
 *   • File selection for agent context
 *   • Filter/search by filename
 *   • Breadcrumb navigation
 *   • Sorting: folders first, then files alphabetically
 */

import { useMemo } from "react";
import { useAgentStore } from "../store/agentStore";
import type { FileEntry } from "../types";

interface FileTreeProps {
  onClose: () => void;
  onFilesSelected: (paths: string[]) => void;
}

// ── File icon by extension (matches QML icon map) ──
function getFileIcon(name: string, isDir: boolean, isLink: boolean): string {
  if (isLink) return "🔗";
  if (isDir) return "📁";
  const ext = name.split(".").pop()?.toLowerCase() || "";
  const iconMap: Record<string, string> = {
    qml: "🟢", py: "🐍", js: "📜", ts: "🔷", json: "📋",
    md: "📝", cpp: "⚙️", cxx: "⚙️", cc: "⚙️", h: "📄", hpp: "📄",
    go: "🔵", rs: "🦀", sh: "💻", yaml: "📄", yml: "📄",
    toml: "⚙️", cmake: "⚙️", xml: "📄", svg: "🖼️",
    png: "🖼️", jpg: "🖼️", jpeg: "🖼️", gif: "🖼️",
  };
  return iconMap[ext] || "📄";
}

// ── Format file size (matches QML) ──
function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1048576).toFixed(1)} MB`;
}

// ── Format date (matches QML) ──
function formatDate(timestamp: number): string {
  return new Date(timestamp * 1000).toLocaleDateString();
}

export default function FileTree({ onClose, onFilesSelected }: FileTreeProps) {
  const fileEntries = useAgentStore((s) => s.fileEntries);
  const selectedFiles = useAgentStore((s) => s.selectedFiles);
  const currentDir = useAgentStore((s) => s.currentDir);
  const filterText = useAgentStore((s) => s.filterText);
  const loadingFiles = useAgentStore((s) => s.loadingFiles);
  const toggleFileSelection = useAgentStore((s) => s.toggleFileSelection);
  const navigateTo = useAgentStore((s) => s.navigateTo);
  const goBack = useAgentStore((s) => s.goBack);
  const history = useAgentStore((s) => s.history);
  const setFilterText = useAgentStore((s) => s.setFilterText);

  // Build breadcrumb from currentDir
  const breadcrumbs = useMemo(() => {
    const parts = currentDir.split("/").filter(Boolean);
    const crumbs: { label: string; path: string }[] = [];
    let acc = "";
    for (const p of parts) {
      acc += "/" + p;
      crumbs.push({ label: p || "/", path: acc });
    }
    return crumbs;
  }, [currentDir]);

  // Filter and sort: folders first, then files alphabetically (matches QML rebuildVisibleModel)
  const visibleEntries = useMemo(() => {
    const filtered = filterText
      ? fileEntries.filter((e) => e.name.toLowerCase().includes(filterText.toLowerCase()))
      : fileEntries;
    const folders = filtered.filter((e) => e.isDir).sort((a, b) => a.name.localeCompare(b.name));
    const files = filtered.filter((e) => !e.isDir).sort((a, b) => a.name.localeCompare(b.name));
    return [...folders, ...files];
  }, [fileEntries, filterText]);

  const handleItemClick = (entry: FileEntry) => {
    if (entry.isDir) {
      navigateTo(entry.path);
    }
  };

  const handleDoubleClick = (entry: FileEntry) => {
    if (!entry.isDir) {
      toggleFileSelection(entry.path);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ backgroundColor: "rgba(0,0,0,0.5)" }}
      onClick={onClose}
    >
      <div
        className="w-[480px] max-h-[70vh] rounded-lg shadow-2xl flex flex-col overflow-hidden"
        style={{
          backgroundColor: "var(--bg-primary, #232629)",
          border: "1px solid var(--border-color, rgba(255,255,255,0.1))",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center gap-2 px-3 py-2 border-b" style={{ borderColor: "var(--border-color)" }}>
          <button
            onClick={goBack}
            disabled={history.length === 0}
            className="p-1 rounded hover:opacity-80 disabled:opacity-30"
            style={{ color: "var(--text-secondary)" }}
            title="Go Back"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="15 18 9 12 15 6" />
            </svg>
          </button>
          <button
            className="p-1 rounded hover:opacity-80"
            style={{ color: "var(--text-secondary)" }}
            title="Home"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
              <polyline points="9 22 9 12 15 12 15 22" />
            </svg>
          </button>
          <div
            className="flex-1 text-sm font-medium truncate"
            style={{ color: "var(--text-primary)" }}
          >
            Context Files
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded hover:opacity-80"
            style={{ color: "var(--text-secondary)" }}
            title="Close"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {/* Breadcrumb */}
        {breadcrumbs.length > 0 && (
          <div
            className="flex items-center gap-1 px-3 py-1.5 text-xs border-b overflow-x-auto"
            style={{ borderColor: "var(--border-color)", color: "var(--text-disabled)" }}
          >
            {breadcrumbs.map((crumb, i) => (
              <span key={crumb.path} className="flex items-center gap-1 flex-shrink-0">
                <button
                  onClick={() => navigateTo(crumb.path)}
                  className="hover:underline"
                  style={{ color: "var(--text-secondary)" }}
                >
                  {crumb.label}
                </button>
                {i < breadcrumbs.length - 1 && <span>›</span>}
              </span>
            ))}
          </div>
        )}

        {/* Search / filter */}
        <div className="px-3 py-2">
          <input
            type="text"
            value={filterText}
            onChange={(e) => setFilterText(e.target.value)}
            placeholder="Filter files..."
            className="w-full px-3 py-1.5 text-sm rounded-md outline-none"
            style={{
              backgroundColor: "var(--bg-input, rgba(0,0,0,0.2))",
              border: "1px solid var(--border-color)",
              color: "var(--text-primary)",
            }}
          />
        </div>

        {/* File list */}
        <div className="flex-1 overflow-y-auto px-1 min-h-[200px]">
          {loadingFiles ? (
            <div className="flex items-center justify-center py-8">
              <div className="animate-spin w-6 h-6 border-2 border-t-transparent rounded-full" style={{ borderColor: "var(--accent-color, #3DAEE9)", borderTopColor: "transparent" }} />
            </div>
          ) : visibleEntries.length === 0 ? (
            <div className="text-center py-8 text-sm" style={{ color: "var(--text-disabled)" }}>
              No files
            </div>
          ) : (
            visibleEntries.map((entry) => {
              const isSelected = selectedFiles.includes(entry.path);
              return (
                <div
                  key={entry.path}
                  onClick={() => handleItemClick(entry)}
                  onDoubleClick={() => handleDoubleClick(entry)}
                  className="flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer transition-colors"
                  style={{
                    backgroundColor: isSelected
                      ? "rgba(61, 174, 233, 0.1)"
                      : "transparent",
                  }}
                  onMouseEnter={(e) => {
                    if (!isSelected) e.currentTarget.style.backgroundColor = "rgba(255,255,255,0.05)";
                  }}
                  onMouseLeave={(e) => {
                    if (!isSelected) e.currentTarget.style.backgroundColor = "transparent";
                  }}
                >
                  {/* Checkbox for files */}
                  {!entry.isDir && (
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => toggleFileSelection(entry.path)}
                      className="flex-shrink-0"
                      style={{ accentColor: "#3DAEE9" }}
                    />
                  )}

                  {/* Icon */}
                  <span className="text-sm flex-shrink-0 w-5 text-center">
                    {getFileIcon(entry.name, entry.isDir, entry.isLink)}
                  </span>

                  {/* Name + details */}
                  <div className="flex-1 min-w-0">
                    <div
                      className="text-sm truncate"
                      style={{
                        color: entry.isLink
                          ? "#3DAEE9"
                          : "var(--text-primary, #eff1f5)",
                        fontWeight: entry.isDir ? 600 : 400,
                      }}
                    >
                      {entry.name}
                    </div>
                    {!entry.isDir && (
                      <div
                        className="text-xs"
                        style={{ color: "var(--text-disabled, #7f8c8d)" }}
                      >
                        {formatSize(entry.size)} • {formatDate(entry.mtime)}
                      </div>
                    )}
                  </div>

                  {/* Arrow for directories */}
                  {entry.isDir && (
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--text-disabled, #7f8c8d)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="9 18 15 12 9 6" />
                    </svg>
                  )}
                </div>
              );
            })
          )}
        </div>

        {/* Bottom bar */}
        <div
          className="flex items-center justify-between px-3 py-2 border-t"
          style={{ borderColor: "var(--border-color)" }}
        >
          <span className="text-xs" style={{ color: "var(--text-disabled)" }}>
            {selectedFiles.length === 0
              ? "Select files for context"
              : `${selectedFiles.length} file(s) selected`}
          </span>
          <button
            onClick={() => onFilesSelected(selectedFiles)}
            disabled={selectedFiles.length === 0}
            className="px-3 py-1 text-xs rounded-md transition-colors disabled:opacity-30"
            style={{
              backgroundColor: selectedFiles.length > 0 ? "var(--accent-color, #3DAEE9)" : "transparent",
              color: selectedFiles.length > 0 ? "#fff" : "var(--text-disabled)",
              border: "1px solid var(--border-color)",
            }}
          >
            Add Selected
          </button>
        </div>
      </div>
    </div>
  );
}
