import datetime
from pathlib import Path
from typing import Optional


class WeeklyReportAgent:
    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is not None:
            self._data_dir = Path(data_dir)
        else:
            from huaqi_src.config.paths import require_data_dir
            self._data_dir = require_data_dir()

        self._register_providers()

    def _register_providers(self) -> None:
        from huaqi_src.layers.capabilities.reports.providers import _registry, register
        from huaqi_src.layers.capabilities.reports.providers.diary import DiaryProvider
        from huaqi_src.layers.capabilities.reports.providers.people import PeopleProvider
        from huaqi_src.layers.capabilities.reports.providers.learning import LearningProvider
        from huaqi_src.layers.capabilities.reports.providers.growth import GrowthProvider

        for p in list(_registry):
            if p.name in ("diary", "people", "learning", "growth"):
                _registry.remove(p)

        register(DiaryProvider(self._data_dir))
        register(PeopleProvider(self._data_dir))
        register(LearningProvider(self._data_dir))
        register(GrowthProvider(self._data_dir))

    def _build_context(self) -> str:
        from huaqi_src.layers.capabilities.reports.providers import DateRange
        from huaqi_src.layers.capabilities.reports.context_builder import build_context
        today = datetime.date.today()
        week_start = today - datetime.timedelta(days=6)
        date_range = DateRange(start=week_start, end=today)
        return build_context("weekly", date_range)

    def _generate_report(self) -> str:
        from langchain_core.messages import SystemMessage, HumanMessage
        from huaqi_src.cli.context import build_llm_manager

        context = self._build_context()
        llm_mgr = build_llm_manager(temperature=0.7, max_tokens=800)
        if llm_mgr is None:
            return "（LLM 未配置，无法生成周报）"

        active_name = llm_mgr.get_active_provider()
        if not active_name:
            return "（未配置任何 LLM 提供商）"
        cfg = llm_mgr._configs[active_name]

        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(
            model=cfg.model,
            api_key=cfg.api_key,
            base_url=cfg.api_base or None,
            temperature=0.7,
            max_tokens=800,
        )

        system_prompt = (
            "你是 huaqi，用户的 AI 同伴。请根据以下背景信息，生成一份本周成长报告，"
            "包含：1）本周成长亮点，2）目标进展，3）值得关注的关系动态，4）下周建议。"
            "报告不超过 600 字，语气温暖有洞察力。"
        )

        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"背景信息：\n{context}"),
        ])
        return response.content

    def run(self) -> str:
        report = self._generate_report()
        report_dir = self._data_dir / "reports" / "weekly"
        report_dir.mkdir(parents=True, exist_ok=True)
        today = datetime.date.today()
        iso = today.isocalendar()
        week_str = f"{iso[0]}-W{iso[1]:02d}"
        report_file = report_dir / f"{week_str}.md"
        report_file.write_text(f"# 周报 {week_str}\n\n{report}\n", encoding="utf-8")
        return report
