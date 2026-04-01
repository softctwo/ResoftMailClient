from __future__ import annotations

import os
import sys
from pathlib import Path


def load_env(env_path: str | Path | None = None) -> Path:
    base_dir = Path(__file__).resolve().parent
    path = Path(env_path) if env_path else base_dir / ".env.eas"
    if not path.exists():
        raise FileNotFoundError(f"未找到配置文件: {path}")

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ[key.strip()] = value.strip()

    return path


def add_import_path() -> Path:
    base_dir = Path(__file__).resolve().parent
    src_root = base_dir / "src"
    sys.path.insert(0, str(src_root))
    return src_root
