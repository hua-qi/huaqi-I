"""用户数据提取器

启动时从多数据源（画像、日记、对话历史）异步提取用户信息，
不阻塞用户输入，失败时自动重试。
"""

import json
import re
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from huaqi_src.core.config_paths import get_memory_dir


class UserDataExtractor:
    """启动时从多数据源提取用户信息

    异步执行，不阻塞用户输入。失败时自动重试，直到成功。
    """

    MAX_RETRIES = 3
    RETRY_DELAY_BASE = 2.0
    LLM_TIMEOUT = 30

    def __init__(self, memory_dir: Optional[Path] = None):
        self.memory_dir = memory_dir or get_memory_dir()
        self._extraction_result: Optional[Dict[str, Any]] = None
        self._extraction_thread: Optional[threading.Thread] = None
        self._is_extracting = False
        self._retry_count = 0
        self._last_error: Optional[str] = None
        self._on_status_update: Optional[Callable[[str], None]] = None

    def _notify_status(self, message: str):
        if self._on_status_update:
            try:
                self._on_status_update(message)
            except Exception:
                pass

    def _collect_user_data(self) -> Dict[str, Any]:
        """收集所有用户相关数据"""
        from huaqi_src.core.profile_manager import get_profile_manager

        data = {
            "profile": {},
            "recent_diaries": [],
            "recent_conversations": [],
            "last_extraction": None
        }

        try:
            profile_manager = get_profile_manager()
            profile = profile_manager.profile
            data["profile"] = {
                "identity": profile.identity.to_dict(),
                "preferences": profile.preferences.to_dict(),
                "background": profile.background.to_dict(),
                "extraction_history_count": len(profile.extraction_history)
            }
            if profile.extraction_history:
                data["last_extraction"] = profile.extraction_history[-1].get("timestamp")
        except Exception:
            pass

        try:
            from huaqi_src.core.diary_simple import DiaryStore
            diary_store = DiaryStore(self.memory_dir)
            recent_diaries = diary_store.list_entries(limit=5)
            data["recent_diaries"] = [
                {
                    "date": d.date,
                    "content_preview": d.content[:200] + "..." if len(d.content) > 200 else d.content,
                    "mood": d.mood,
                    "tags": d.tags
                }
                for d in recent_diaries
            ]
        except Exception:
            pass

        try:
            from huaqi_src.memory.storage.markdown_store import MarkdownMemoryStore
            conv_store = MarkdownMemoryStore(self.memory_dir / "conversations")
            conversations = conv_store.list_conversations(limit=3)
            data["recent_conversations"] = [
                {
                    "session_id": c.get("session_id", ""),
                    "created_at": c.get("created_at", ""),
                    "turns": c.get("turns", 0)
                }
                for c in conversations[:3]
            ]
        except Exception:
            pass

        return data

    def _build_extraction_prompt(self, user_data: Dict[str, Any]) -> str:
        profile_info = user_data.get("profile", {})
        diaries = user_data.get("recent_diaries", [])
        conversations = user_data.get("recent_conversations", [])
        last_extraction = user_data.get("last_extraction")

        diary_text = ""
        if diaries:
            diary_lines = []
            for d in diaries[:3]:
                diary_lines.append(f"【{d['date']}】")
                if d.get("mood"):
                    diary_lines.append(f"情绪: {d['mood']}")
                if d.get("tags"):
                    diary_lines.append(f"标签: {', '.join(d['tags'])}")
                diary_lines.append(f"内容: {d['content_preview']}")
                diary_lines.append("")
            diary_text = "\n".join(diary_lines)

        conv_text = ""
        if conversations:
            conv_lines = [f"- 会话 {c['session_id'][:8]}... ({c['turns']} 轮)" for c in conversations[:3]]
            conv_text = "\n".join(conv_lines)

        return f"""分析用户的日记和对话历史，提取用户的个人信息。

规则：
1. 只提取明确提到的信息，不要猜测
2. 如果用户说"我叫子蒙"，提取 name="子蒙"
3. 如果用户说"我是一名工程师"，提取 occupation="工程师"
4. 如果用户说"喜欢阅读"，提取 hobbies=["阅读"]
5. 如果没有新信息，返回空对象 {{}}
6. 不要覆盖已有信息，只补充新信息

当前已知的用户信息：
```json
{json.dumps(profile_info, ensure_ascii=False, indent=2)}
```

最近日记：
{diary_text or "无"}

最近对话历史：
{conv_text or "无"}

上次提取时间：{last_extraction or "从未"}

请提取新的用户信息，以 JSON 格式返回：
{{
    "name": "名字",
    "nickname": "昵称",
    "occupation": "职业",
    "location": "所在地",
    "company": "公司",
    "skills": ["技能1", "技能2"],
    "hobbies": ["爱好1", "爱好2"],
    "life_goals": ["目标1"],
    "education": "教育背景",
    "family_info": "家庭信息"
}}

只返回 JSON，不要其他内容。"""

    def start_extraction(
        self,
        llm_manager,
        on_complete: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_status: Optional[Callable[[str], None]] = None
    ):
        """启动异步提取（后台线程，不阻塞）"""
        if self._is_extracting:
            return

        self._is_extracting = True
        self._on_status_update = on_status

        def _extract_worker():
            try:
                result = self._extract_with_llm(llm_manager)
                self._extraction_result = result
                if on_complete:
                    on_complete(result)
            except Exception:
                self._extraction_result = {}
                if on_complete:
                    on_complete({})
            finally:
                self._is_extracting = False
                self._on_status_update = None

        self._extraction_thread = threading.Thread(target=_extract_worker, daemon=True)
        self._extraction_thread.start()

    def _extract_with_llm_once(self, llm_manager) -> Dict[str, Any]:
        """单次 LLM 提取"""
        from huaqi_src.core.llm import Message
        from huaqi_src.core.profile_manager import get_profile_manager

        user_data = self._collect_user_data()
        prompt = self._build_extraction_prompt(user_data)

        messages = [
            Message.system("你是用户信息分析助手，从日记和对话中提取结构化信息。"),
            Message.user(prompt)
        ]

        response = llm_manager.chat(messages)
        content = response.content.strip()

        if "```" in content:
            lines = content.split("\n")
            json_lines = []
            in_json = False
            for line in lines:
                if line.strip().startswith("```"):
                    in_json = not in_json
                    continue
                if in_json:
                    json_lines.append(line)
            if json_lines:
                content = "\n".join(json_lines)

        extracted = json.loads(content.strip())
        extracted = {k: v for k, v in extracted.items() if v and v not in ([], "", None, "null")}

        list_fields = ['skills', 'hobbies', 'life_goals', 'values']
        for f in list_fields:
            if f in extracted and isinstance(extracted[f], str):
                extracted[f] = [extracted[f]]

        if extracted:
            profile_manager = get_profile_manager()
            profile_manager._apply_extraction(extracted, "startup_analysis")

        return extracted

    def _extract_with_llm(self, llm_manager) -> Dict[str, Any]:
        """使用 LLM 提取用户信息（带重试机制）"""
        self._retry_count = 0
        self._last_error = None

        while self._retry_count < self.MAX_RETRIES:
            try:
                self._notify_status(f"正在分析用户数据... (尝试 {self._retry_count + 1}/{self.MAX_RETRIES})")
                result = self._extract_with_llm_once(llm_manager)

                if result:
                    self._notify_status(f"✓ 已提取: {', '.join(result.keys())}")
                    return result
                else:
                    self._notify_status("✓ 分析完成，无新信息")
                    return {}

            except Exception as e:
                self._last_error = str(e)
                self._retry_count += 1

                if self._retry_count < self.MAX_RETRIES:
                    delay = self.RETRY_DELAY_BASE * (2 ** (self._retry_count - 1))
                    self._notify_status(f"提取失败，{delay:.0f}秒后重试... ({self._retry_count}/{self.MAX_RETRIES})")
                    for _ in range(int(delay * 10)):
                        if not self._is_extracting:
                            return {}
                        time.sleep(0.1)
                else:
                    self._notify_status(f"✗ 提取失败，已达到最大重试次数 ({self.MAX_RETRIES})")
                    break

        self._notify_status("切换到兜底方案...")
        fallback_result = self._extract_with_fallback()
        if fallback_result:
            self._notify_status(f"✓ 兜底方案提取: {', '.join(fallback_result.keys())}")
        else:
            self._notify_status("✓ 兜底方案无新信息")
        return fallback_result

    def _extract_with_fallback(self) -> Dict[str, Any]:
        """兜底提取方案：基于规则的关键词匹配"""
        from huaqi_src.core.profile_manager import get_profile_manager

        extracted = {}

        try:
            diary_data = self._collect_user_data().get("recent_diaries", [])
            for diary in diary_data:
                content = diary.get("content_preview", "")
                patterns = [
                    (r'我是([\u4e00-\u9fa5]{2,4})', 'name'),
                    (r'我叫([\u4e00-\u9fa5]{2,4})', 'name'),
                    (r'昵称[是为]?([\u4e00-\u9fa5\w]{1,6})', 'nickname'),
                    (r'([\u4e00-\u9fa5]{2,6})工程师', 'occupation'),
                    (r'职业[是为]([^，。]{2,10})', 'occupation'),
                    (r'住在([^，。]{2,10})', 'location'),
                    (r'在([^，。]{2,10})工作', 'company'),
                    (r'公司[是为]([^，。]{2,10})', 'company'),
                    (r'我会([\u4e00-\u9fa5\w\s,]+)', 'skills'),
                    (r'擅长([\u4e00-\u9fa5\w\s,]+)', 'skills'),
                    (r'喜欢([\u4e00-\u9fa5\w\s,]+)', 'hobbies'),
                    (r'爱好([\u4e00-\u9fa5\w\s,]+)', 'hobbies'),
                ]

                for pattern, field_name in patterns:
                    matches = re.findall(pattern, content)
                    if matches:
                        value = matches[0].strip()
                        if value and len(value) >= 2:
                            if field_name in ['skills', 'hobbies']:
                                items = [v.strip() for v in re.split(r'[,，、和]', value) if len(v.strip()) >= 2]
                                if items:
                                    extracted[field_name] = list(set(extracted.get(field_name, []) + items))
                            else:
                                extracted[field_name] = value
        except Exception:
            pass

        if extracted:
            try:
                profile_manager = get_profile_manager()
                profile_manager._apply_extraction(extracted, "fallback_analysis")
            except Exception:
                pass

        return extracted

    def is_extracting(self) -> bool:
        return self._is_extracting

    def get_result(self) -> Optional[Dict[str, Any]]:
        return self._extraction_result

    def get_retry_count(self) -> int:
        return self._retry_count

    def get_last_error(self) -> Optional[str]:
        return self._last_error

    def cancel_extraction(self):
        self._is_extracting = False
        if self._extraction_thread and self._extraction_thread.is_alive():
            self._extraction_thread.join(timeout=1.0)

    def wait_for_completion(self, timeout: float = 60.0) -> Dict[str, Any]:
        """等待提取完成（阻塞，带超时）"""
        if self._extraction_thread and self._extraction_thread.is_alive():
            self._extraction_thread.join(timeout=timeout)
        return self._extraction_result or {}


_data_extractor: Optional[UserDataExtractor] = None


def get_data_extractor() -> UserDataExtractor:
    """获取全局数据提取器"""
    global _data_extractor
    if _data_extractor is None:
        _data_extractor = UserDataExtractor()
    return _data_extractor


def init_data_extractor(memory_dir: Optional[Path] = None) -> UserDataExtractor:
    """初始化全局数据提取器"""
    global _data_extractor
    _data_extractor = UserDataExtractor(memory_dir)
    return _data_extractor


def extract_user_info_on_startup(llm_manager, timeout: float = 15.0) -> Dict[str, Any]:
    """启动时提取用户信息（简化调用）"""
    extractor = get_data_extractor()

    if extractor.is_extracting():
        return extractor.wait_for_completion(timeout)

    if extractor.get_result() is not None:
        return extractor.get_result()

    result_container: Dict[str, Any] = {}

    def _on_complete(result):
        result_container['result'] = result

    extractor.start_extraction(llm_manager, on_complete=_on_complete)
    extractor.wait_for_completion(timeout)

    return result_container.get('result', {}) or extractor.get_result() or {}
