import datetime
from pathlib import Path
from typing import Optional


class DailyReportAgent:
    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is not None:
            self._data_dir = Path(data_dir)
        else:
            from huaqi_src.config.paths import require_data_dir
            self._data_dir = require_data_dir()

        self._register_providers()

    def _register_providers(self) -> None:
        from huaqi_src.layers.capabilities.reports.providers import _registry, register
        from huaqi_src.layers.capabilities.reports.providers.world import WorldProvider
        from huaqi_src.layers.capabilities.reports.providers.diary import DiaryProvider
        from huaqi_src.layers.capabilities.reports.providers.people import PeopleProvider

        for p in list(_registry):
            if p.name in ("world", "diary", "people"):
                _registry.remove(p)

        register(WorldProvider(self._data_dir))
        register(DiaryProvider(self._data_dir))
        register(PeopleProvider(self._data_dir))

    def _build_context(self) -> str:
        from huaqi_src.layers.capabilities.reports.providers import DateRange
        from huaqi_src.layers.capabilities.reports.context_builder import build_context
        today = datetime.date.today()
        date_range = DateRange(start=today, end=today)
        return build_context("daily", date_range)

    def _generate_report(self) -> str:
        from langchain_core.messages import SystemMessage, HumanMessage
        from huaqi_src.cli.context import build_llm_manager

        context = self._build_context()
        llm_mgr = build_llm_manager(temperature=0.7, max_tokens=600)
        if llm_mgr is None:
            return "（LLM 未配置，无法生成复盘）"

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
            max_tokens=600,
        )

        system_prompt = (
            "你是 huaqi，用户的 AI 同伴。请根据以下背景信息，生成一份简洁的日终复盘报告，"
            "包含：1）今日主要收获和亮点，2）情绪和状态观察，3）明日建议。"
            "报告应简短，不超过 400 字，语气温暖。"
        )

        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"背景信息：\n{context}"),
        ])
        return response.content

    def run(self) -> str:
        report = self._generate_report()
        report_dir = self._data_dir / "reports" / "daily"
        report_dir.mkdir(parents=True, exist_ok=True)
        today = datetime.date.today().isoformat()
        report_file = report_dir / f"{today}-evening.md"
        report_file.write_text(f"# 日终复盘 {today}\n\n{report}\n", encoding="utf-8")
        return report
