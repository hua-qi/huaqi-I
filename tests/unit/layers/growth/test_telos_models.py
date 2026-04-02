import pytest
from pydantic import ValidationError

from huaqi_src.layers.growth.telos.models import (
    TelosDimension,
    DimensionLayer,
    STANDARD_DIMENSIONS,
    STANDARD_DIMENSION_LAYERS,
)


class TestDimensionLayer:
    def test_core_layer_exists(self):
        assert DimensionLayer.CORE == "core"

    def test_middle_layer_exists(self):
        assert DimensionLayer.MIDDLE == "middle"

    def test_surface_layer_exists(self):
        assert DimensionLayer.SURFACE == "surface"


class TestStandardDimensions:
    def test_nine_standard_dimensions(self):
        assert len(STANDARD_DIMENSIONS) == 9

    def test_core_layer_dimensions(self):
        core = [d for d, l in STANDARD_DIMENSION_LAYERS.items() if l == DimensionLayer.CORE]
        assert set(core) == {"beliefs", "models", "narratives"}

    def test_middle_layer_dimensions(self):
        middle = [d for d, l in STANDARD_DIMENSION_LAYERS.items() if l == DimensionLayer.MIDDLE]
        assert set(middle) == {"goals", "challenges", "strategies"}

    def test_surface_layer_dimensions(self):
        surface = [d for d, l in STANDARD_DIMENSION_LAYERS.items() if l == DimensionLayer.SURFACE]
        assert set(surface) == {"learned", "people", "shadows"}


class TestTelosDimensionCreation:
    def test_minimal_valid_dimension(self):
        dim = TelosDimension(
            name="beliefs",
            layer=DimensionLayer.CORE,
            content="选择比努力更重要。",
        )
        assert dim.name == "beliefs"
        assert dim.layer == DimensionLayer.CORE
        assert dim.content == "选择比努力更重要。"

    def test_confidence_defaults_to_half(self):
        dim = TelosDimension(
            name="goals",
            layer=DimensionLayer.MIDDLE,
            content="完成 MVP",
        )
        assert dim.confidence == 0.5

    def test_update_count_defaults_to_zero(self):
        dim = TelosDimension(
            name="beliefs",
            layer=DimensionLayer.CORE,
            content="测试",
        )
        assert dim.update_count == 0

    def test_history_defaults_to_empty(self):
        dim = TelosDimension(
            name="beliefs",
            layer=DimensionLayer.CORE,
            content="测试",
        )
        assert dim.history == []

    def test_is_active_defaults_to_true(self):
        dim = TelosDimension(
            name="beliefs",
            layer=DimensionLayer.CORE,
            content="测试",
        )
        assert dim.is_active is True

    def test_custom_dimension_allowed(self):
        dim = TelosDimension(
            name="health",
            layer=DimensionLayer.SURFACE,
            content="关注身体状态",
            is_custom=True,
        )
        assert dim.is_custom is True
        assert dim.name == "health"

    def test_standard_dimension_not_custom(self):
        dim = TelosDimension(
            name="beliefs",
            layer=DimensionLayer.CORE,
            content="测试",
        )
        assert dim.is_custom is False


class TestTelosDimensionValidation:
    def test_confidence_below_zero_raises(self):
        with pytest.raises(ValidationError):
            TelosDimension(
                name="beliefs",
                layer=DimensionLayer.CORE,
                content="测试",
                confidence=-0.1,
            )

    def test_confidence_above_one_raises(self):
        with pytest.raises(ValidationError):
            TelosDimension(
                name="beliefs",
                layer=DimensionLayer.CORE,
                content="测试",
                confidence=1.1,
            )

    def test_empty_content_raises(self):
        with pytest.raises(ValidationError):
            TelosDimension(
                name="beliefs",
                layer=DimensionLayer.CORE,
                content="",
            )

    def test_empty_name_raises(self):
        with pytest.raises(ValidationError):
            TelosDimension(
                name="",
                layer=DimensionLayer.CORE,
                content="测试",
            )


class TestTelosDimensionHistory:
    def test_add_history_entry(self):
        from huaqi_src.layers.growth.telos.models import HistoryEntry
        from datetime import datetime, timezone

        dim = TelosDimension(
            name="beliefs",
            layer=DimensionLayer.CORE,
            content="新认知",
        )
        entry = HistoryEntry(
            version=1,
            change="从 A 变成 B",
            trigger="连续 3 次日记提到",
            confidence=0.75,
            updated_at=datetime(2026, 1, 4, tzinfo=timezone.utc),
        )
        dim.history.append(entry)
        assert len(dim.history) == 1
        assert dim.history[0].version == 1

    def test_update_count_reflects_history_length(self):
        from huaqi_src.layers.growth.telos.models import HistoryEntry
        from datetime import datetime, timezone

        dim = TelosDimension(
            name="beliefs",
            layer=DimensionLayer.CORE,
            content="认知 v3",
        )
        for i in range(3):
            dim.history.append(HistoryEntry(
                version=i + 1,
                change=f"变化 {i}",
                trigger="触发",
                confidence=0.7,
                updated_at=datetime(2026, 1, i + 1, tzinfo=timezone.utc),
            ))
        assert len(dim.history) == 3


class TestTelosDimensionMarkdown:
    def test_to_markdown_contains_frontmatter(self):
        dim = TelosDimension(
            name="beliefs",
            layer=DimensionLayer.CORE,
            content="选择比努力更重要。",
            confidence=0.82,
        )
        md = dim.to_markdown()
        assert "dimension: beliefs" in md
        assert "layer: core" in md
        assert "confidence: 0.82" in md

    def test_to_markdown_contains_content(self):
        dim = TelosDimension(
            name="beliefs",
            layer=DimensionLayer.CORE,
            content="选择比努力更重要。",
        )
        md = dim.to_markdown()
        assert "选择比努力更重要" in md

    def test_from_markdown_roundtrip(self):
        dim = TelosDimension(
            name="beliefs",
            layer=DimensionLayer.CORE,
            content="选择比努力更重要。",
            confidence=0.82,
            update_count=3,
        )
        md = dim.to_markdown()
        restored = TelosDimension.from_markdown(md)
        assert restored.name == dim.name
        assert restored.layer == dim.layer
        assert restored.confidence == dim.confidence
        assert restored.content.strip() == dim.content.strip()
