# Spec: TELOS 蒸馏质量优化

> 优化 TELOS 引擎的维度提炼质量，解决核心层空洞、维度坍缩、版本膨胀/语言虚浮三个结构性问题。

## 1. 要解决的问题

763 条历史信号处理后，TELOS 八个标准维度出现三类结构性缺陷：

1. **核心层空洞**：beliefs 和 models 两个核心维度仍为「（待补充）」，760+ 条信号无一触发。根本原因是 step1 对核心层的触发标准过高——要求用户明确说出「我相信/我认为」才算，而现实中价值观和世界观更多通过行为选择、决策理由、隐含前提表达。
2. **维度坍缩**：narratives、goals、strategies、challenges 四个维度的当前认知本质上在描述同一件事——「用户把与 Huaqi 的对话当作元认知工具」。原因是少量强自我揭示信号被 LLM 套用到所有维度上，维度之间缺乏互斥约束。
3. **版本膨胀与语言虚浮**：goals v97、strategies v68、learned v151，大量版本是对同一批信号的措辞改写，内容无实质变化。语言越来越抽象（「元认知的元认知」「存在实验室」），违反「写给用户自己看」的设计初衷。

## 2. 功能范围

**包含：**
- 优化 step1 prompt：降低核心层触发门槛，支持隐含信念/世界观的识别；限制每条信号最多匹配 2 个维度；允许 medium 信号积累触发核心层初始化
- 优化 step345 prompt：加当前认知段字数上限（≤150 字）；禁止高频抽象词；要求引用具体信号内容；加关联点验证逻辑
- 引擎层：保持已有的 95% 相似度跳过和 history cap（已完成，不重复）
- 同步更新 `_defaults.py` 中的内置回退提示词

**不包含：**
- 代码层面的强去重（用户选择仅 prompt 约束）
- 重构 TelosManager 或 Engine 架构
- 维度体系的重新设计（STANDARD_DIMENSIONS 不变）
- 数据目录中已有维度文件的手工重写——优化后的 prompt 会在后续更新中自然改善

## 3. 验收标准

**AC: 核心层空洞**
- [ ] AC-1: step1 prompt 中核心层触发条件扩展为「用户表达了明确的价值观声明 OR 行为选择中隐含了信念假设 OR 对某事做出了是非/对错的判断」，不再要求字面意义上的「我相信」
- [ ] AC-2: step1 prompt 中增加说明——medium 信号若持续指向同一维度，允许触发该维度的首次初始化
- [ ] AC-3: `huaqi_src/prompts/_defaults.py` 中 step1 内置回退同步更新

**AC: 维度坍缩**
- [ ] AC-4: step1 prompt 中增加维度匹配数量限制——每条信号最多匹配 2 个维度，超过时只保留 signal_strength 最高的 2 个
- [ ] AC-5: step345 prompt 中增加「关联点验证」——要求 LLM 在决定更新前，先回答「这批信号中哪一条具体与当前维度关联，关联点是什么」，无法指定具体信号则 should_update=false
- [ ] AC-6: `huaqi_src/prompts/_defaults.py` 中 step345 内置回退同步更新

**AC: 版本膨胀/语言虚浮**
- [ ] AC-7: step345 prompt 中 new_content 字数上限 ≤300 字，且要求引用至少一条具体信号内容
- [ ] AC-8: step345 prompt 中禁止使用「元认知」「跃迁」「校准」「共建」「范式」「涌现」等抽象术语，要求用日常口语替代
- [ ] AC-9: `huaqi_src/prompts/_defaults.py` 中 step345 内置回退同步更新

**AC: 回归保护**
- [ ] AC-10: `pytest tests/unit/layers/growth/ -v` 全部通过
- [ ] AC-11: `pytest tests/smoke_test.py -v` 全部通过

## 4. 依赖

- 依赖：`huaqi_src/prompts/_defaults.py`（已存在）、`huaqi_src/layers/growth/telos/engine.py`（已存在）
- 数据目录 prompt 文件：`{data_dir}/prompts/layers/growth/telos/engine/step1.md`、`step345.md`
- 后续依赖：未来新增中间层维度时，需继承本 spec 中的互斥约束和字数限制规则

## 5. 风险与假设

- **假设**：核心层信号确实存在于 763 条历史数据中，只是未被识别——降低门槛后应能触发
- **风险**：降低核心层门槛后可能产生过于琐碎或错误的 beliefs/models 内容——依赖 confidence 机制兜底
- **风险**：字数上限可能限制 LLM 对复杂认知的描述——300 字是经验值，后续可调
- **假设**：禁止抽象词后 LLM 能找到替代的口语表达——如果不理想，后续迭代中放宽
