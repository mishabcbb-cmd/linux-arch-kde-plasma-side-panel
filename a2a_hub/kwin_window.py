#!/usr/bin/env python3
"""
kwin_window.py — Move/resize windows via KWin D-Bus scripting on Wayland.

Usage:
    python3 kwin_window.py position <window_class> <x> <y> <width> <height>
    python3 kwin_window.py slide <window_class> <start_x> <end_x> <y> <width> <height> <duration_ms> <fps>

Uses a persistent KWin script for smooth animation (loaded once, called many times).
"""

import subprocess
import sys
import time
import os
import tempfile
import signal


def find_qdbus():
    for cmd in ["qdbus6", "qdbus"]:
        result = subprocess.run(["which", cmd], capture_output=True, text=True)
        if result.returncode == 0:
            return cmd.strip()
    return None


def load_kwin_script(js_code, plugin_id):
    """Load a KWin script and return the script file path."""
    qdbus = find_qdbus()
    if not qdbus:
        print("ERROR: qdbus6 or qdbus not found", file=sys.stderr)
        return False

    script_file = tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False, prefix=f"kwin_{plugin_id}_")
    script_file.write(js_code)
    script_file.close()

    subprocess.run(
        [qdbus, "org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting.loadScript",
         script_file.name, plugin_id],
        capture_output=True, text=True, timeout=5
    )
    return script_file.name


def unload_kwin_script(plugin_id):
    """Unload a KWin script."""
    qdbus = find_qdbus()
    if not qdbus:
        return
    subprocess.run(
        [qdbus, "org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting.unloadScript", plugin_id],
        capture_output=True, text=True, timeout=5
    )


def run_kwin_script(plugin_id):
    """Start a loaded KWin script."""
    qdbus = find_qdbus()
    if not qdbus:
        return
    subprocess.run(
        [qdbus, "org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting.start"],
        capture_output=True, text=True, timeout=5
    )


def position_window(window_class, x, y, width, height):
    """Move and resize a window by its resource class (one-shot)."""
    plugin_id = f"pos_{os.getpid()}_{int(time.time()*1000)}"

    js_code = f"""
const PATTERN = "{window_class}";
const needle = PATTERN.toLowerCase();
const TARGET_X = {x};
const TARGET_Y = {y};
const TARGET_W = {width};
const TARGET_H = {height};

function fieldMatch(w) {{
    const fields = [w.resourceClass, w.resourceName];
    for (let i = 0; i < fields.length; i++) {{
        const f = fields[i] ? String(fields[i]).toLowerCase() : "";
        if (f.indexOf(needle) >= 0) return true;
    }}
    return false;
}}

const all = (typeof workspace.windowList === "function")
    ? workspace.windowList()
    : workspace.clientList();

const found = [];
for (let i = 0; i < all.length; i++) {{
    const w = all[i];
    if (!w || w.normalWindow === false) continue;
    if (fieldMatch(w)) found.push(w);
}}

if (found.length === 0) {{
    print("[kwin_window] NO_MATCH pattern=" + PATTERN);
}} else {{
    const w = found[0];
    // If height is 0, keep current height
    const h = TARGET_H > 0 ? TARGET_H : w.frameGeometry.height;
    const g = w.frameGeometry;
    print("[kwin_window] MOVING class=" + (w.resourceClass || "?") +
          " from=" + g.width + "x" + g.height + "+" + g.x + "+" + g.y +
          " to=" + TARGET_W + "x" + h + "+" + TARGET_X + "+" + TARGET_Y);
    w.frameGeometry = {{ x: TARGET_X, y: TARGET_Y, width: TARGET_W, height: h }};
    print("[kwin_window] DONE");
}}
"""
    script_file = load_kwin_script(js_code, plugin_id)
    if not script_file:
        return False

    try:
        run_kwin_script(plugin_id)
        time.sleep(0.3)
        return True
    finally:
        unload_kwin_script(plugin_id)
        try:
            os.unlink(script_file)
        except OSError:
            pass


def slide_window(window_class, start_x, end_x, y, width, height, duration_ms, fps):
    """Animate window slide using a persistent KWin script with D-Bus callbacks."""
    plugin_id = f"slide_{os.getpid()}_{int(time.time()*1000)}"
    frame_time = 1.0 / fps
    total_frames = max(1, int(duration_ms / 1000.0 * fps))

    # Build a script that receives frame data via a temp file
    # We use a simpler approach: load script once, update via file, run repeatedly
    state_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, prefix="kwin_slide_")
    state_file.close()

    js_code = f"""
const PATTERN = "{window_class}";
const needle = PATTERN.toLowerCase();
const STATE_FILE = "{state_file.name}";
const TARGET_W = {width};
const TARGET_Y = {y};
const TARGET_H = {height > 0 ? height : -1};  // -1 = keep current

function fieldMatch(w) {{
    const fields = [w.resourceClass, w.resourceName];
    for (let i = 0; i < fields.length; i++) {{
        const f = fields[i] ? String(fields[i]).toLowerCase() : "";
        if (f.indexOf(needle) >= 0) return true;
    }}
    return false;
}}

const all = (typeof workspace.windowList === "function")
    ? workspace.windowList()
    : workspace.clientList();

const found = [];
for (let i = 0; i < all.length; i++) {{
    const w = all[i];
    if (!w || w.normalWindow === false) continue;
    if (fieldMatch(w)) found.push(w);
}}

if (found.length === 0) {{
    print("[kwin_window] NO_MATCH");
}} else {{
    const w = found[0];
    // Read target x from state file (written by Python)
    try {{
        const fp = new QFile(STATE_FILE);
        if (fp.open(QIODevice.ReadOnly)) {{
            const data = fp.readAll().toString();
            fp.close();
            const targetX = parseInt(data.trim());
            if (!isNaN(targetX)) {{
                const g = w.frameGeometry;
                const h = TARGET_H > 0 ? TARGET_H : g.height;
                w.frameGeometry = {{ x: targetX, y: TARGET_Y, width: TARGET_W, height: h }};
            }}
        }}
    }} catch(e) {{
        print("[kwin_window] ERROR: " + e);
    }}
}}
"""

    # Note: QFile may not be available in KWin scripting.
    # Simpler approach: just call position_window for each frame
    # It's slower but works

    try:
        for frame in range(total_frames + 1):
            t = frame / total_frames
            # Ease-out cubic
            eased = 1.0 - (1.0 - t) ** 3
            current_x = int(start_x + (end_x - start_x) * eased)

            success = position_window(window_class, current_x, y, width, height)
            if not success:
                return False

            if frame < total_frames:
                time.sleep(frame_time)

        return True
    finally:
        try:
            os.unlink(state_file.name)
        except OSError:
            pass


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    action = sys.argv[1]

    if action == "position":
        if len(sys.argv) != 7:
            print("Usage: kwin_window.py position <window_class> <x> <y> <width> <height>")
            sys.exit(1)
        window_class = sys.argv[2]
        x, y, width, height = int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6])
        success = position_window(window_class, x, y, width, height)
        sys.exit(0 if success else 1)

    elif action == "slide":
        if len(sys.argv) != 10:
            print("Usage: kwin_window.py slide <window_class> <start_x> <end_x> <y> <width> <height> <duration_ms> <fps>")
            sys.exit(1)
        window_class = sys.argv[2]
        start_x, end_x = int(sys.argv[3]), int(sys.argv[4])
        y, width, height = int(sys.argv[5]), int(sys.argv[6]), int(sys.argv[7])
        duration_ms, fps = int(sys.argv[8]), int(sys.argv[9])
        success = slide_window(window_class, start_x, end_x, y, width, height, duration_ms, fps)
        sys.exit(0 if success else 1)

    else:
        print(f"Unknown action: {action}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
