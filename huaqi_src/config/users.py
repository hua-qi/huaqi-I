import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List
from uuid import uuid4

from pydantic import BaseModel

from huaqi_src.config.errors import UserNotFoundError


class UserProfile(BaseModel):
    id: str
    name: str
    created_at: datetime
    data_dir: str


class UserContext(BaseModel):
    profile: UserProfile
    telos_dir: Path
    raw_files_dir: Path
    db_path: Path
    vector_dir: Path

    model_config = {"arbitrary_types_allowed": True}

    @classmethod
    def from_profile(cls, profile: UserProfile, base_dir: Path) -> "UserContext":
        user_dir = base_dir / profile.name
        return cls(
            profile=profile,
            telos_dir=user_dir / "telos",
            raw_files_dir=user_dir / "raw_files",
            db_path=user_dir / "signals.db",
            vector_dir=user_dir / "vectors",
        )


class UserManager:

    def __init__(self, config_dir: Path) -> None:
        self._config_dir = config_dir
        self._users_file = config_dir / "users.json"

    def _load(self) -> Dict:
        if not self._users_file.exists():
            return {"current": None, "profiles": {}}
        return json.loads(self._users_file.read_text(encoding="utf-8"))

    def _save(self, data: Dict) -> None:
        self._config_dir.mkdir(parents=True, exist_ok=True)
        self._users_file.write_text(
            json.dumps(data, indent=2, default=str),
            encoding="utf-8",
        )

    def create(self, name: str) -> UserProfile:
        data = self._load()
        if name in data["profiles"]:
            return UserProfile(**data["profiles"][name])
        profile = UserProfile(
            id=str(uuid4()),
            name=name,
            created_at=datetime.now(timezone.utc),
            data_dir=str(Path("~/.huaqi/data") / name),
        )
        data["profiles"][name] = profile.model_dump()
        if data["current"] is None:
            data["current"] = name
        self._save(data)
        return profile

    def get(self, name: str) -> UserProfile:
        data = self._load()
        if name not in data["profiles"]:
            raise UserNotFoundError(f"User '{name}' not found")
        return UserProfile(**data["profiles"][name])

    def get_current(self) -> UserProfile:
        data = self._load()
        if not data["current"]:
            raise UserNotFoundError("No current user set")
        return self.get(data["current"])

    def switch(self, name: str) -> None:
        data = self._load()
        if name not in data["profiles"]:
            raise UserNotFoundError(f"User '{name}' not found")
        data["current"] = name
        self._save(data)

    def list_all(self) -> List[UserProfile]:
        data = self._load()
        return [UserProfile(**p) for p in data["profiles"].values()]
