"""Writable preferences and executable discovery, including Finder's minimal PATH."""

import json
import os
import shutil
import threading
from pathlib import Path

from .errors import CCAskError

_PREFERENCES_LOCK = threading.RLock()


def preferences(settings):
    try:
        data = json.loads((settings.data_dir / "preferences.json").read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def codex_path(settings):
    configured = os.environ.get("CCASK_CODEX_EXECUTABLE") or preferences(settings).get("codex_path")
    if configured:
        path = Path(configured).expanduser()
        return str(path.resolve()) if path.is_file() and os.access(path, os.X_OK) else None
    home = Path.home()
    candidates = [
        shutil.which("codex"),
        "/opt/homebrew/bin/codex",
        "/usr/local/bin/codex",
        home / ".local/bin/codex",
        home / ".npm-global/bin/codex",
        "/Applications/Codex.app/Contents/Resources/codex",
        home / "Applications/Codex.app/Contents/Resources/codex",
    ]
    candidates += sorted((home / ".nvm/versions/node").glob("*/bin/codex"), reverse=True)
    candidates += sorted(
        (home / ".local/share/fnm/node-versions").glob("*/installation/bin/codex"), reverse=True
    )
    for candidate in candidates:
        if candidate and Path(candidate).is_file() and os.access(candidate, os.X_OK):
            # Keep the symlink directory: npm's /usr/bin/env node needs its sibling node.
            return str(Path(candidate).absolute())
    return None


def executable_env(executable):
    paths = [
        str(Path(executable).parent),
        "/opt/homebrew/bin",
        "/usr/local/bin",
        "/usr/bin",
        "/bin",
        "/usr/sbin",
        "/sbin",
        os.environ.get("PATH", ""),
    ]
    return {**os.environ, "PATH": os.pathsep.join(paths)}


def update_preferences(settings, updates):
    with _PREFERENCES_LOCK:
        settings.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        data = {**preferences(settings), **updates}
        path = settings.data_dir / "preferences.json"
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False))
        temporary.chmod(0o600)
        temporary.replace(path)


def save_codex_path(settings, value):
    if value:
        path = Path(value).expanduser()
        if not path.is_absolute() or not path.is_file() or not os.access(path, os.X_OK):
            raise CCAskError("请填写可执行的 codex 文件的完整路径。", "invalid_codex_path")
        value = str(path.absolute())
    update_preferences(settings, {"codex_path": value})
    return {"codex_path": codex_path(settings)}
