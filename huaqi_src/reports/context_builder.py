from huaqi_src.reports.providers import DateRange, get_providers


def build_context(report_type: str, date_range: DateRange) -> str:
    parts = [
        ctx
        for p in get_providers(report_type)
        if (ctx := p.get_context(report_type, date_range))
    ]
    return "\n\n".join(parts) if parts else "暂无上下文数据。"
