"""
端到端测试：真实 LLM 验证 Telos 流水线

需要有效的 LLM 配置才能运行。
运行方式：pytest tests/e2e/ -v -m e2e
"""
import pytest
from pathlib import Path
from datetime import datetime, timezone


pytestmark = pytest.mark.e2e


@pytest.fixture
def telos_dir(tmp_path: Path) -> Path:
    d = tmp_path / "telos"
    d.mkdir()
    return d


@pytest.fixture
def real_llm():
    try:
        from huaqi_src.cli.context import build_llm_manager, ensure_initialized
        ensure_initialized()
        llm_mgr = build_llm_manager(temperature=0.3, max_tokens=2000)
        if llm_mgr is None:
            pytest.skip("未配置 LLM")
        active_name = llm_mgr.get_active_provider()
        cfg = llm_mgr._configs[active_name]
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=cfg.model,
            api_key=cfg.api_key,
            base_url=cfg.api_base or None,
            temperature=0.3,
            max_tokens=2000,
        )
    except Exception as e:
        pytest.skip(f"LLM 配置失败: {e}")


def test_step1_real_llm_parses_journal(telos_dir, real_llm):
    from huaqi_src.layers.growth.telos.manager import TelosManager
    from huaqi_src.layers.growth.telos.engine import TelosEngine, Step1Output, SignalStrength
    from huaqi_src.layers.data.raw_signal.models import RawSignal, SourceType

    mgr = TelosManager(telos_dir=telos_dir, git_commit=False)
    mgr.init()
    engine = TelosEngine(telos_manager=mgr, llm=real_llm)

    signal = RawSignal(
        user_id="user_e2e",
        source_type=SourceType.JOURNAL,
        timestamp=datetime.now(timezone.utc),
        content="今天突然想清楚了一件事：我一直在拼命努力，但从来没有停下来想方向对不对。感觉选错了方向，努力是白费的。",
    )

    result = engine.step1_analyze(signal)

    assert isinstance(result, Step1Output)
    assert len(result.dimensions) > 0
    assert any(d in ["challenges", "goals", "beliefs"] for d in result.dimensions)
    assert result.signal_strength in [SignalStrength.STRONG, SignalStrength.MEDIUM]


def test_step345_combined_real_llm(telos_dir, real_llm):
    from huaqi_src.layers.growth.telos.manager import TelosManager
    from huaqi_src.layers.growth.telos.engine import TelosEngine, CombinedStepOutput

    mgr = TelosManager(telos_dir=telos_dir, git_commit=False)
    mgr.init()
    engine = TelosEngine(telos_manager=mgr, llm=real_llm)

    result = engine.step345_combined(
        dimension="challenges",
        signal_summaries=[
            "用户对方向感感到迷茫，质疑努力的意义",
            "用户觉得选错了方向，努力都是白费的",
            "用户想停下来重新思考目标和方向",
        ],
        days=7,
        recent_signal_count=3,
    )

    assert isinstance(result, CombinedStepOutput)
    assert isinstance(result.should_update, bool)
    assert 0.0 <= result.confidence <= 1.0
    assert 0.0 <= result.consistency_score <= 1.0


def test_telos_snapshot_in_agent_context_real_llm(telos_dir, real_llm):
    from huaqi_src.layers.growth.telos.manager import TelosManager
    from huaqi_src.layers.growth.telos.engine import TelosEngine
    from huaqi_src.layers.growth.telos.context import TelosContextBuilder

    mgr = TelosManager(telos_dir=telos_dir, git_commit=False)
    mgr.init()
    engine = TelosEngine(telos_manager=mgr, llm=real_llm)

    engine.step345_combined(
        dimension="beliefs",
        signal_summaries=["选择比努力重要", "方向错了努力没用"],
        days=7,
        recent_signal_count=2,
    )

    builder = TelosContextBuilder(telos_manager=mgr)
    snapshot = builder.build_telos_snapshot()

    assert "beliefs" in snapshot
    assert len(snapshot) > 50
