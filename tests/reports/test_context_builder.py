import datetime
from huaqi_src.reports.providers import _registry, DateRange


def test_build_context_combines_providers():
    _registry.clear()

    from huaqi_src.reports.providers import register, DataProvider

    class FakeProvider1(DataProvider):
        name = "fake1"
        priority = 10
        supported_reports = ["daily"]

        def get_context(self, report_type, date_range):
            return "数据A"

    class FakeProvider2(DataProvider):
        name = "fake2"
        priority = 20
        supported_reports = ["daily"]

        def get_context(self, report_type, date_range):
            return "数据B"

    register(FakeProvider1())
    register(FakeProvider2())

    from huaqi_src.reports.context_builder import build_context
    today = datetime.date.today()
    date_range = DateRange(start=today, end=today)
    result = build_context("daily", date_range)
    assert "数据A" in result
    assert "数据B" in result


def test_build_context_skips_none_providers():
    _registry.clear()

    from huaqi_src.reports.providers import register, DataProvider

    class EmptyProvider(DataProvider):
        name = "empty"
        priority = 10
        supported_reports = ["daily"]

        def get_context(self, report_type, date_range):
            return None

    class RealProvider(DataProvider):
        name = "real"
        priority = 20
        supported_reports = ["daily"]

        def get_context(self, report_type, date_range):
            return "真实数据"

    register(EmptyProvider())
    register(RealProvider())

    from huaqi_src.reports.context_builder import build_context
    today = datetime.date.today()
    date_range = DateRange(start=today, end=today)
    result = build_context("daily", date_range)
    assert "真实数据" in result
    assert result.count("\n\n") == 0


def test_build_context_returns_fallback_when_all_none():
    _registry.clear()

    from huaqi_src.reports.context_builder import build_context
    from huaqi_src.reports.providers import DateRange
    today = datetime.date.today()
    date_range = DateRange(start=today, end=today)
    result = build_context("daily", date_range)
    assert result == "暂无上下文数据。"
