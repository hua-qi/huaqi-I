import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import pytest

from huaqi_src.layers.data.raw_signal.models import RawSignal, SourceType
from huaqi_src.layers.growth.telos.dimensions.people.pipeline import PeoplePipeline
from huaqi_src.layers.growth.telos.dimensions.people.graph import PeopleGraph
from huaqi_src.layers.growth.telos.dimensions.people.models import Person


@pytest.fixture
def graph(tmp_path: Path) -> PeopleGraph:
    return PeopleGraph(data_dir=tmp_path)


@pytest.fixture
def signal() -> RawSignal:
    return RawSignal(
        user_id="u1",
        source_type=SourceType.JOURNAL,
        timestamp=datetime.now(timezone.utc),
        content="今天和张伟一起推进了产品评审，进展很顺利。",
    )


async def test_pipeline_appends_interaction_log_to_existing_person(graph, signal):
    existing = Person(person_id="p1", name="张伟", relation_type="同事")
    graph.add_person(existing)

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content=json.dumps([
        {
            "name": "张伟",
            "interaction_type": "合作",
            "emotional_score": 0.6,
            "summary": "一起推进了产品评审",
            "new_profile": None,
            "new_relation_type": None,
        }
    ])))

    pipeline = PeoplePipeline(graph=graph, llm=mock_llm)
    await pipeline.process(signal=signal, mentioned_names=["张伟"])

    updated = graph.get_person("张伟")
    assert updated is not None
    assert len(updated.interaction_logs) == 1
    assert updated.interaction_logs[0].interaction_type == "合作"
    assert updated.interaction_logs[0].signal_id == signal.id


async def test_pipeline_appends_emotional_timeline_to_existing_person(graph, signal):
    existing = Person(person_id="p1", name="张伟", relation_type="同事")
    graph.add_person(existing)

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content=json.dumps([
        {
            "name": "张伟",
            "interaction_type": "合作",
            "emotional_score": 0.7,
            "summary": "进展顺利",
            "new_profile": None,
            "new_relation_type": None,
        }
    ])))

    pipeline = PeoplePipeline(graph=graph, llm=mock_llm)
    await pipeline.process(signal=signal, mentioned_names=["张伟"])

    updated = graph.get_person("张伟")
    assert len(updated.emotional_timeline) == 1
    assert abs(updated.emotional_timeline[0].score - 0.7) < 0.001


async def test_pipeline_creates_new_person_via_extractor_when_unknown(graph, signal):
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content=json.dumps([
        {
            "name": "新人物",
            "interaction_type": "初识",
            "emotional_score": 0.5,
            "summary": "第一次见面",
            "new_profile": "工程师",
            "new_relation_type": "同事",
        }
    ])))

    mock_extractor = MagicMock()
    new_person = Person(person_id="pnew", name="新人物", relation_type="同事", profile="工程师")
    mock_extractor.extract_from_text.return_value = [new_person]

    pipeline = PeoplePipeline(graph=graph, llm=mock_llm, person_extractor=mock_extractor)
    await pipeline.process(signal=signal, mentioned_names=["新人物"])

    mock_extractor.extract_from_text.assert_called_once()


async def test_pipeline_makes_single_llm_call_for_multiple_names(graph, signal):
    for name in ["张伟", "李四"]:
        graph.add_person(Person(person_id=name, name=name, relation_type="同事"))

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content=json.dumps([
        {"name": "张伟", "interaction_type": "合作", "emotional_score": 0.5, "summary": "s1", "new_profile": None, "new_relation_type": None},
        {"name": "李四", "interaction_type": "日常", "emotional_score": 0.3, "summary": "s2", "new_profile": None, "new_relation_type": None},
    ])))

    pipeline = PeoplePipeline(graph=graph, llm=mock_llm)
    await pipeline.process(signal=signal, mentioned_names=["张伟", "李四"])

    assert mock_llm.ainvoke.call_count == 1


async def test_pipeline_returns_empty_list_on_llm_parse_error(graph, signal):
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="不是合法JSON"))

    pipeline = PeoplePipeline(graph=graph, llm=mock_llm)
    result = await pipeline.process(signal=signal, mentioned_names=["张伟"])
    assert result == []
