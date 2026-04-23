from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


FAVORITES_FILE = Path("data/parameter_favorites.json")


@dataclass(frozen=True, slots=True)
class FavoriteParameter:
    name: str
    group: str = "Custom"
    access: str = "Unknown"
    description: str = ""
    notes: str = ""


class FavoriteStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or FAVORITES_FILE

    def load(self) -> list[FavoriteParameter]:
        if not self.path.exists():
            return []

        raw = json.loads(self.path.read_text(encoding="utf-8"))
        return [FavoriteParameter(**item) for item in raw]

    def save(self, favorites: list[FavoriteParameter]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = [asdict(item) for item in favorites]
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
