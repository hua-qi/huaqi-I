import pytest
from pathlib import Path
from huaqi_src.config.users import UserProfile, UserContext, UserManager


def test_user_manager_creates_profile(tmp_path):
    manager = UserManager(config_dir=tmp_path)
    profile = manager.create("alice")

    assert profile.name == "alice"
    assert len(profile.id) == 36
    assert (tmp_path / "users.json").exists()


def test_user_manager_get_current(tmp_path):
    manager = UserManager(config_dir=tmp_path)
    manager.create("alice")
    current = manager.get_current()
    assert current.name == "alice"


def test_user_manager_switch(tmp_path):
    manager = UserManager(config_dir=tmp_path)
    manager.create("alice")
    manager.create("bob")
    manager.switch("bob")
    assert manager.get_current().name == "bob"


def test_user_context_paths(tmp_path):
    manager = UserManager(config_dir=tmp_path)
    profile = manager.create("alice")
    ctx = UserContext.from_profile(profile, base_dir=tmp_path / "data")

    assert ctx.telos_dir == tmp_path / "data" / "alice" / "telos"
    assert ctx.db_path == tmp_path / "data" / "alice" / "signals.db"
    assert ctx.vector_dir == tmp_path / "data" / "alice" / "vectors"
