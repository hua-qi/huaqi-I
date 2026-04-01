import datetime
from pathlib import Path
from typing import Optional


class MorningBriefAgent:
    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is not None:
            self._data_dir = Path(data_dir)
        else:
            from huaqi_src.core.config_paths import require_data_dir
            self._data_dir = require_data_dir()

        self._register_providers()

    def _register_providers(self) -> None:
        from huaqi_src.reports.providers import _registry, register
        from huaqi_src.reports.providers.world import WorldProvider
        from huaqi_src.reports.providers.diary import DiaryProvider
        from huaqi_src.reports.providers.people import PeopleProvider

        for p in list(_registry):
            if p.name in ("world", "diary", "people"):
                _registry.remove(p)

        register(WorldProvider(self._data_dir))
        register(DiaryProvider(self._data_dir))
        register(PeopleProvider(self._data_dir))

    def _build_context(self) -> str:
        from huaqi_src.reports.providers import DateRange
        from huaqi_src.reports.context_builder import build_context
        today = datetime.date.today()
        date_range = DateRange(start=today, end=today)
        return build_context("morning", date_range)

    def _generate_brief(self) -> str:
        from langchain_core.messages import SystemMessage, HumanMessage

        context = self._build_context()

        from huaqi_src.cli.context import build_llm_manager
        llm_mgr = build_llm_manager(temperature=0.7, max_tokens=500)
        if llm_mgr is None:
            return "（LLM 未配置，无法生成简报）"

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
            max_tokens=500,
        )

        system_prompt = (
            "你是 huaqi，用户的 AI 同伴。请根据以下背景信息，生成一份简洁温暖的晨间简报，"
            "包含：1）今日世界热点摘要（如有），2）对用户近期状态的简短观察，3）一句鼓励的话。"
            "简报应简短，不超过 300 字。"
        )

        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"背景信息：\n{context}"),
        ])
        return response.content

    def run(self) -> str:
        brief = self._generate_brief()

        report_dir = self._data_dir / "reports" / "daily"
        report_dir.mkdir(parents=True, exist_ok=True)

        today = datetime.date.today().isoformat()
        report_file = report_dir / f"{today}-morning.md"
        report_file.write_text(
            f"# 晨间简报 {today}\n\n{brief}\n",
            encoding="utf-8",
        )

        return brief
