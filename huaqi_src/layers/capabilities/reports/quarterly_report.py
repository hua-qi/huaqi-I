import datetime
from pathlib import Path
from typing import Optional


class QuarterlyReportAgent:
    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is None:
            from huaqi_src.config.paths import require_data_dir
            data_dir = require_data_dir()
        self.data_dir = Path(data_dir)

        self._register_providers()

    def _register_providers(self) -> None:
        from huaqi_src.layers.capabilities.reports.providers import _registry, register
        from huaqi_src.layers.capabilities.reports.providers.people import PeopleProvider
        from huaqi_src.layers.capabilities.reports.providers.growth import GrowthProvider
        from huaqi_src.layers.capabilities.reports.providers.weekly_reports import WeeklyReportsProvider
        from huaqi_src.layers.capabilities.reports.providers.learning import LearningProvider

        for p in list(_registry):
            if p.name in ("people", "growth", "weekly_reports", "learning"):
                _registry.remove(p)

        register(PeopleProvider(self.data_dir))
        register(GrowthProvider(self.data_dir))
        register(WeeklyReportsProvider(self.data_dir))
        register(LearningProvider(self.data_dir))

    def _current_quarter(self) -> tuple:
        today = datetime.date.today()
        return today.year, (today.month - 1) // 3 + 1

    def _build_context(self) -> str:
        from huaqi_src.layers.capabilities.reports.providers import DateRange
        from huaqi_src.layers.capabilities.reports.context_builder import build_context
        today = datetime.date.today()
        quarter_start = today - datetime.timedelta(weeks=13)
        date_range = DateRange(start=quarter_start, end=today)
        return build_context("quarterly", date_range)

    def _generate_report(self) -> str:
        from langchain_core.messages import SystemMessage, HumanMessage
        from huaqi_src.cli.context import build_llm_manager

        context = self._build_context()
        llm_mgr = build_llm_manager(temperature=0.7, max_tokens=1200)
        if llm_mgr is None:
            return "（LLM 未配置，无法生成季报）"

        if not llm_mgr._active_provider:
            return "（未配置任何 LLM 提供商）"
        cfg = llm_mgr._active_provider.config

        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(
            model=cfg.model,
            api_key=cfg.api_key,
            base_url=cfg.api_base or None,
            temperature=0.7,
            max_tokens=1200,
        )

        system_prompt = (
            "你是 huaqi，用户的 AI 同伴。请根据以下背景信息，生成一份季度成长报告，"
            "包含：1）本季度核心成长，2）长期模式识别（正向/需改善），3）目标漂移分析，"
            "4）关系网络变化，5）下季度建议。报告不超过 800 字，有深度有洞察。"
        )

        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"背景信息：\n{context}"),
        ])
        return response.content

    def run(self) -> str:
        report = self._generate_report()
        report_dir = self.data_dir / "reports" / "quarterly"
        report_dir.mkdir(parents=True, exist_ok=True)
        year, quarter = self._current_quarter()
        report_file = report_dir / f"{year}-Q{quarter}.md"
        report_file.write_text(f"# 季报 {year}-Q{quarter}\n\n{report}\n", encoding="utf-8")
        return report
