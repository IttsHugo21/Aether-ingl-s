from __future__ import annotations

from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


def load_sectors(path: Path | None = None) -> dict[str, dict]:
    with open(path or CONFIG_DIR / "sectors.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_blocklist(path: Path | None = None) -> list[str]:
    p = path or CONFIG_DIR / "blocklist.txt"
    if not p.exists():
        return []
    lines = p.read_text(encoding="utf-8").splitlines()
    return [l.strip().lower() for l in lines if l.strip() and not l.startswith("#")]


def build_queries(
    sectors: dict[str, dict], selected: list[str] | None, extra_keywords: list[str] | None
) -> list[tuple[str, str]]:
    """Devuelve (sector, keyword) sin duplicados, respetando el orden."""
    keys = selected or list(sectors)
    unknown = [k for k in keys if k not in sectors]
    if unknown:
        raise SystemExit(
            f"Sector(es) desconocido(s): {', '.join(unknown)}. "
            f"Disponibles: {', '.join(sectors)}"
        )
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for key in keys:
        for kw in sectors[key]["keywords"]:
            if kw.lower() not in seen:
                seen.add(kw.lower())
                out.append((key, kw))
    for kw in extra_keywords or []:
        if kw.lower() not in seen:
            seen.add(kw.lower())
            out.append(("custom", kw))
    return out
