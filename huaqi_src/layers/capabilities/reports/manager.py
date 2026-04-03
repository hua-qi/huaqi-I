import datetime
from pathlib import Path
from typing import Optional
from huaqi_src.layers.capabilities.reports.morning_brief import MorningBriefAgent
from huaqi_src.layers.capabilities.reports.daily_report import DailyReportAgent
from huaqi_src.layers.capabilities.reports.weekly_report import WeeklyReportAgent
from huaqi_src.layers.capabilities.reports.quarterly_report import QuarterlyReportAgent
from huaqi_src.config.paths import require_data_dir

class ReportManager:
    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or require_data_dir()
        self.reports_dir = self.data_dir / "reports"

    def get_or_generate_report(self, report_type: str, date_str: str = "today", force: bool = False) -> str:
        today = datetime.date.today()
        if date_str == "today":
            target_date = today
        elif date_str == "yesterday":
            target_date = today - datetime.timedelta(days=1)
        else:
            try:
                target_date = datetime.date.fromisoformat(date_str)
            except ValueError:
                return f"日期格式错误: {date_str}，请使用 YYYY-MM-DD"
            
        date_iso = target_date.isoformat()
        
        mapping = {
            "morning": ("daily", f"{date_iso}-morning.md", MorningBriefAgent),
            "daily": ("daily", f"{date_iso}-evening.md", DailyReportAgent),
            "weekly": ("weekly", f"{date_iso}-weekly.md", WeeklyReportAgent),
            "quarterly": ("quarterly", f"{date_iso}-quarterly.md", QuarterlyReportAgent),
        }
        
        if report_type not in mapping:
            return f"未知的报告类型: {report_type}"
            
        subdir, filename, agent_class = mapping[report_type]
        file_path = self.reports_dir / subdir / filename
        
        if not force and file_path.exists():
            return file_path.read_text(encoding="utf-8")
            
        if target_date != today:
            return f"无法生成历史日期的报告: {date_iso}，且未找到已有文件。"
            
        # 实时生成
        agent = agent_class(data_dir=self.data_dir)
        try:
            agent.run()
        except Exception as e:
            return f"报告生成失败: {str(e)}"
        
        if file_path.exists():
            return file_path.read_text(encoding="utf-8")
        
        return "报告已触发生成，但未找到输出文件。"
