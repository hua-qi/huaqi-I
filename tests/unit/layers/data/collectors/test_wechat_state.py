from huaqi_src.layers.data.collectors.wechat_state import WeChatSyncState


def test_get_last_rowid_returns_zero_for_unknown_db(tmp_path):
    state = WeChatSyncState(state_file=tmp_path / "wechat_state.json")
    assert state.get_last_rowid("msg_0.db") == 0


def test_set_and_get_last_rowid(tmp_path):
    state = WeChatSyncState(state_file=tmp_path / "wechat_state.json")
    state.set_last_rowid("msg_0.db", 42)
    assert state.get_last_rowid("msg_0.db") == 42


def test_state_persists_across_instances(tmp_path):
    state_file = tmp_path / "wechat_state.json"
    state1 = WeChatSyncState(state_file=state_file)
    state1.set_last_rowid("msg_1.db", 100)

    state2 = WeChatSyncState(state_file=state_file)
    assert state2.get_last_rowid("msg_1.db") == 100


def test_multiple_dbs_tracked_independently(tmp_path):
    state = WeChatSyncState(state_file=tmp_path / "wechat_state.json")
    state.set_last_rowid("msg_0.db", 10)
    state.set_last_rowid("msg_1.db", 99)
    assert state.get_last_rowid("msg_0.db") == 10
    assert state.get_last_rowid("msg_1.db") == 99
