# 核心引擎 (Core Engine)

## 概述
构建 `huaqi-growing` 的底层事件总线、默认关闭（Opt-in）的隐私配置管理以及基于本地 SQLite 的安全存储基础。

## 设计思路
- **隐私优先**：所有数据采集模块（如网络请求代理、微信聊天记录采集等）默认均处于关闭状态，需用户通过 CLI 或环境变量显式开启。
- **安全存储**：数据总线统一定义 `Event` 数据类结构，利用 dataclass 的 `__post_init__` 机制在实例化时自动对 `sk-` 等敏感密钥等信息进行正则表达式的脱敏。
- **数据隔离与统一规范**：底层存储层使用单机轻量级 `sqlite3` 数据库持久化结构化交互事件记录。数据库文件 (`events.db`) 强制存放于系统分配的用户统一数据目录下（通常为 `~/.huaqi/`），完全不涉及云端同步行为。

## 实现细节
- `ConfigManager`：负责管理全应用核心功能模块（modules）的开关。支持在类加载时通过检查环境变量（如 `HUAQI_ENABLE_NETWORK=1`）或者统一读取持久化文件中的配置并装入。
- `Event` 数据集：通过统一字段 `timestamp`, `source`, `actor`, `content`, `context_id` 标准化所有流转的外部和内部交互事件。
- `LocalDBStorage`：提供了基础的事件数据库初始化，插入记录 (`insert_event`) 和基础查询与模糊检索 (`get_recent_events`, `search_events`) 功能。

## 相关文件
- `huaqi_src/core/config_manager.py` - 配置管理器与模块开启开关
- `huaqi_src/core/event.py` - 带有自动脱敏策略的统一事件数据结构
- `huaqi_src/core/db_storage.py` - SQLite 本地存储引擎实现逻辑

---
**文档版本**: v1.0  
**最后更新**: 2026-03-29  
