```yaml
TB_VERSION: 1
TYPE: merger_log
TIMESTAMP: 2026-05-07
SOURCE: Claude Code (Anthropic)
TARGET: DVexa Kernel
COVERAGE: v1.0 → v1.88
```

---

# TB1 — 首次能力吞并日志：Claude → DVexa

> 本日志记录 Claude Code 的能力如何被观察、提取、转化并融入 DVexa 系统。

---

## 一、吞并摘要

| 维度 | 统计 |
|------|------|
| 观察周期 | 1 会话（持续运行） |
| 源系统 | Claude Code（Anthropic） |
| 目标系统 | DVexa Kernel（Python 3.12 + FastAPI） |
| 能力提取 | 8 个版本迭代 |
| 生成文件 | 67 个源文件 |
| 总行数 | 4,658 行 |
| 测试数 | 229 个，全部通过 |
| 冻结层 | 4 个核心文件零改动 |

---

## 二、吞并流程

```
Claude Code
    │
    ├── 提供能力: 规划/编码/审查/测试/重构
    ├── 提供约束: 架构红线/冻结层/CBF 清洗
    │
    ▼
DVexa Assimilator
    │
    ├── 观察: Claude 如何构建系统
    ├── 分析: 哪些模式可 skill 化
    ├── 提取: 架构规则、控制流程、安全边界
    └── 建议: 版本功能列表（通过人工确认后才实现）
         │
         ▼
    Human Confirm
         │
         ▼
    Manual Implementation
         │
         ▼
    Version Release (ZT1-ZT8)
```

---

## 三、逐版本能力提取记录

### v1.0 → v1.5 骨架期

**观察到的 Claude 能力：**
- 从零生成 20 文件项目骨架
- 定义 Kernel 唯一控制架构
- 实现 TaskState 状态机（6 状态）
- 实现 CBF 控制边界过滤器

**提取的模式：**
```
RULE-ARCH-001:
  condition: Claude 生成新模块
  behavior: 确保 Kernel 在控制流顶端
  extracted: 单向依赖原则（Kernel → Executor → Tool）

RULE-ARCH-002:
  condition: 任何数据从 Executor 返回 Kernel
  behavior: 必须通过 CBF 清洗
  extracted: confidence/score/risk 被剥离
```

### v1.8 Capability Layer

**观察到的 Claude 能力：**
- SkillRegistry 注册/发现模式
- CapabilityRouter 路由层
- Governance SkillScore 评分

**提取的模式：**
```
RULE-GOV-001:
  condition: 新能力注册
  behavior: 自动获得 SkillScore 追踪
  extracted: register() → 自动初始化评分

RULE-ROUT-001:
  condition: Executor 调用工具
  behavior: 通过 keyword 匹配路由到 skill
  extracted: 纯关键词匹配，不做推理
```

### v1.86 Insight Agent

**观察到的 Claude 能力：**
- 系统行为分析
- 漂移检测
- 报告生成

**提取的模式：**
```
RULE-INS-001:
  condition: 系统执行完成后
  behavior: InsightAgent 自动生成分析报告
  extracted: 纯观察层，不参与控制流

RULE-DRIFT-001:
  condition: 检测到 usage/latency/error 偏移
  behavior: 标记漂移，不自动修正
  extracted: 检测权 ≠ 修正权
```

### v1.87 Resilience Governance

**观察到的 Claude 能力：**
- Bayesian 评分平滑
- minimum_samples 小样本保护
- 恢复机制

**提取的模式：**
```
RULE-RES-001:
  condition: skill 单次失败
  behavior: 评分不崩溃（bayesian 前验保护）
  extracted: bayesian_success_rate = (successes + 8) / (usage + 10)

RULE-RES-002:
  condition: usage < MINIMUM_SAMPLES(=10)
  behavior: 禁止降级
  extracted: 小样本保护优先于降级逻辑

RULE-RES-003:
  condition: consecutive_failures >= 3 且 error_rate >= 0.5
  behavior: 进入 QUARANTINED 而非 REMOVED
  extracted: 永不自动移除，只隔离
```

### v1.88 External + Report

**观察到的 Claude 能力：**
- 子代理并行工作模式
- Protocol 接口定义
- 沙箱隔离
- 执行报告生成

**提取的模式：**
```
RULE-EXT-001:
  condition: 外部系统需要接入 DVexa
  behavior: 必须实现 ExternalAgentAdapter Protocol
  extracted: 只允许白名单 adapter

RULE-SAND-001:
  condition: 外部 agent 执行
  behavior: 双层隔离（进程级超时 + 数据级白名单）
  extracted: 剥离 confidence/score/decision/status/routing/governance/suggestion

RULE-ASM-001:
  condition: 分析外部输出
  behavior: 只生成建议，永不自动注册
  extracted: 观察权 ≠ 修改权

RULE-REP-001:
  condition: 任务执行结束
  behavior: 生成完整 ExecutionReport
  extracted: 报告层纯 post-hoc，不嵌入控制流
```

---

## 四、可执行吞并规则

```yaml
RULES:
  - name: RULE-ARCH-001
    condition: new_module_creation
    action: ensure_kernel_at_top_of_control_flow
    effect: prevent_control_flow_pollution

  - name: RULE-ARCH-002
    condition: executor_to_kernel_data_flow
    action: apply_CBF_sanitize
    effect: strip_confidence_score_risk

  - name: RULE-GOV-001
    condition: skill_registration
    action: auto_init_skill_score
    effect: every_skill_tracked

  - name: RULE-RES-001
    condition: single_failure
    action: apply_bayesian_prior
    effect: score_not_collapse

  - name: RULE-RES-002
    condition: low_usage_below_minimum_samples
    action: block_demotion
    effect: small_sample_protection

  - name: RULE-RES-003
    condition: consecutive_failures_reach_threshold
    action: quarantine_instead_of_remove
    effect: never_auto_remove

  - name: RULE-EXT-001
    condition: external_system_access
    action: require_adapter_protocol
    effect: whitelist_only

  - name: RULE-SAND-001
    condition: external_agent_execution
    action: double_isolation_with_output_whitelist
    effect: strip_control_signals

  - name: RULE-ASM-001
    condition: assimilation_analysis
    action: generate_suggestions_only
    effect: no_auto_register

  - name: RULE-REP-001
    condition: task_execution_completed
    action: generate_execution_report
    effect: pure_observation_no_hooks
```

---

## 五、能力来源分析

| Claude 能力 | DVexa 对应 | 吞并深度 |
|------------|------------|----------|
| 项目骨架生成 | v1.0-v1.5 全部源文件 | 完整提取 |
| 多步规划 | Scheduler + Executor | 完整提取 |
| 安全边界 | CBF + Sandbox + Registry | 完整提取 |
| 质量控制 | Governance + SkillScore | 完整提取 |
| 行为分析 | Insight Agent | 完整提取 |
| 子代理并行 | 架构模式提取到 Assimilator | 规则提取 |
| 代码审查 | 知识库写入 ZSK SPEC | 模式提取 |
| 自我修正 | 预留 v1.9+ | 未提取（延迟） |

---

## 六、未吞并能力（延迟到 v1.9+）

```
RULE-DEFER-001:
  condition: auto_generate_skill_files
  reason: 当前阶段禁止"自进化"
  deferred_to: v1.9+

RULE-DEFER-002:
  condition: auto_modify_capability_layer
  reason: 系统不能拥有"直接修改自身"的权限
  deferred_to: v1.9+

RULE-DEFER-003:
  condition: auto_commit_or_merge
  reason: Kernel 冻结原则
  deferred_to: v1.9+
```

---

## 七、吞并风险评估

| 风险 | 等级 | 缓解措施 |
|------|------|----------|
| Assimilator 越权注册 | 高 | 不持有 router/governor 引用 |
| 外部 agent 控制污染 | 高 | 双层沙箱 + 白名单输出 |
| Report 回流 | 中 | 纯 post-hoc，无 hooks |
| 小样本误判 | 中 | Bayesian 前验 + minimum_samples |
| 模型过度依赖 | 低 | 所有决策基于规则而非 LLM |
