#!/usr/bin/env python3
"""
filetree_helper.py — Directory listing helper for FileTree.qml.

Called via Plasma5Support.DataSource executable engine.
Usage:
    python3 filetree_helper.py list <directory>

Outputs JSON to stdout with directory contents sorted: folders first, then files.
"""
import json
import os
import sys


def list_directory(path):
    """List immediate contents of a directory, sorted: folders first, then files alphabetically."""
    path = os.path.expanduser(path)
    real_path = os.path.realpath(path)
    items = []

    try:
        entries = sorted(
            os.listdir(path),
            key=lambda x: (
                not os.path.isdir(os.path.join(path, x)),
                x.lower(),
            ),
        )
    except (OSError, PermissionError) as e:
        return {"error": str(e), "path": path, "realPath": real_path, "items": []}

    for entry in entries:
        full_path = os.path.join(path, entry)
        try:
            stat = os.lstat(full_path)
            is_dir = os.path.isdir(full_path)
            is_link = os.path.islink(full_path)
            size = stat.st_size if not is_dir else 0
            mtime = stat.st_mtime
            items.append(
                {
                    "name": entry,
                    "path": full_path,
                    "isDir": is_dir,
                    "isLink": is_link,
                    "size": size,
                    "mtime": mtime,
                }
            )
        except (OSError, PermissionError):
            items.append(
                {
                    "name": entry,
                    "path": full_path,
                    "isDir": False,
                    "isLink": False,
                    "size": 0,
                    "mtime": 0,
                }
            )

    return {"path": path, "realPath": real_path, "items": items}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: filetree_helper.py list <directory>"}))
        sys.exit(1)

    command = sys.argv[1]

    if command == "list":
        path = sys.argv[2] if len(sys.argv) > 2 else "."
        print(json.dumps(list_directory(path)))
    else:
        print(json.dumps({"error": f"Unknown command: {command}"}))
        sys.exit(1)
