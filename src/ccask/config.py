import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    cc_dir: Path
    codex_dir: Path
    timeout: float = 180.0
    sync_interval: float = 5.0

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            data_dir=Path(os.environ.get("CCASK_DATA_DIR", "~/.local/share/ccask")).expanduser(),
            cc_dir=Path(os.environ.get("CCASK_CC_DIR", "~/.cc-switch")).expanduser(),
            codex_dir=Path(os.environ.get("CCASK_CODEX_DIR", "~/.codex")).expanduser(),
            timeout=float(os.environ.get("CCASK_TIMEOUT", "180")),
        )

    @property
    def db_path(self) -> Path:
        return self.data_dir / "ccask.db"
