"""
Workspace file listing and deletion utilities.
"""
import os
import shutil
from dataclasses import dataclass
from typing import Optional

from loguru import logger

import config
from utils.progress_bar import human_size as format_size


@dataclass
class FileEntry:
    index: int
    name: str
    size_bytes: float
    full_path: str


def list_workspace(user_id: int) -> list[FileEntry]:
    """Return all top-level items in user's workspace, sorted by name."""
    ws = config.user_workspace(user_id)
    entries = []
    for idx, name in enumerate(sorted(os.listdir(ws)), start=1):
        full = os.path.join(ws, name)
        try:
            size = _get_size(full)
        except OSError:
            size = 0.0
        entries.append(FileEntry(index=idx, name=name, size_bytes=size, full_path=full))
    return entries


def _get_size(path: str) -> float:
    if os.path.isfile(path):
        return float(os.path.getsize(path))
    total = 0.0
    for dirpath, _, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            try:
                total += os.path.getsize(fp)
            except OSError:
                pass
    return total


def workspace_stats(user_id: int) -> tuple[float, float, float]:
    """Returns (used_bytes, free_bytes, total_bytes)."""
    ws = config.user_workspace(user_id)
    stat = shutil.disk_usage(ws)
    used_by_files = sum(e.size_bytes for e in list_workspace(user_id))
    return used_by_files, float(stat.free), float(stat.total)


def format_workspace_listing(entries: list[FileEntry], user_id: int) -> str:
    used, free, _ = workspace_stats(user_id)
    if not entries:
        lines = ["📂 <b>Workspace is empty.</b>", f"\n💾 Free: {format_size(free)}"]
        return "\n".join(lines)

    lines = [f"📂 <b>Workspace Contents</b> ({format_size(used)} used)\n"]
    for e in entries:
        lines.append(f"  <b>{e.index}.</b> {e.name} — <code>{format_size(e.size_bytes)}</code>")
    lines.append(f"\n💾 Used: {format_size(used)} | Free: {format_size(free)}")
    return "\n".join(lines)


def delete_by_index(index: int, user_id: int) -> tuple[bool, str]:
    """Delete workspace item by 1-based index. Returns (success, message)."""
    entries = list_workspace(user_id)
    if index < 1 or index > len(entries):
        return False, f"❌ Invalid number. Choose between 1 and {len(entries)}."
    entry = entries[index - 1]
    try:
        if os.path.isfile(entry.full_path):
            os.remove(entry.full_path)
        else:
            shutil.rmtree(entry.full_path)
        logger.info(f"Deleted workspace item: {entry.full_path}")
        return True, f"✅ Deleted: <code>{entry.name}</code> ({format_size(entry.size_bytes)})"
    except OSError as e:
        return False, f"❌ Error deleting file: {e}"


def clear_workspace(user_id: int) -> tuple[bool, str]:
    """Delete all items in user's workspace. Returns (success, message)."""
    entries = list_workspace(user_id)
    if not entries:
        return True, "ℹ️ Workspace is already empty."
    errors = []
    for entry in entries:
        try:
            if os.path.isfile(entry.full_path):
                os.remove(entry.full_path)
            else:
                shutil.rmtree(entry.full_path)
        except OSError as e:
            errors.append(str(e))
    if errors:
        return False, f"⚠️ Some files could not be deleted:\n" + "\n".join(errors)
    logger.info(f"Workspace cleared for user {user_id}.")
    return True, "✅ <b>Workspace cleared successfully!</b>"


def has_enough_space(required_bytes: float, user_id: int) -> bool:
    _, free, _ = workspace_stats(user_id)
    return free >= required_bytes


def get_workspace_free_bytes(user_id: int) -> float:
    _, free, _ = workspace_stats(user_id)
    return free
