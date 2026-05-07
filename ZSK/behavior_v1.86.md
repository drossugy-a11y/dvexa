```yaml
ZSK_VERSION: v1.86
TYPE: system_behavior_snapshot
TIMESTAMP: 2026-05-07
```

---

## 1. 系统行为摘要

### LLM 使用分布
```
无生产执行数据（v1.86 新建）。
测试模拟分布（53 次调用）：
  llm:  30 次 (56.6%)  延迟 0.15s  成功率 100%
  code: 15 次 (28.3%)  延迟 0.30s  成功率 100%
  http:  8 次 (15.1%)  延迟 1.06s  成功率 62.5%
```

### Skill 调用分布
```
  llm  → ACTIVE     评分 0.998  30次调用
  code → ACTIVE     评分 0.997  15次调用  
  http → DEPRECATED 评分 0.697   8次调用 (3次超时失败)
```

### Routing 分布
```
  当前 routing 层：keyword → skill_name（一对多）
  3 个 skill，13 个 trigger keyword
  无 routing 冲突检测事件
```

### 代码架构分布
```
  冻结层: Kernel(75) + Executor(75) + CBF(101) + Planner(110) = 361 行
  能力层: capabilities/ = 344 行
  治理层: governance/  = 416 行
  洞察层: insight/     = 340 行
  工具层: tools/       = 203 行
  测试层: tests/       = 1163 行
  总计:   48 文件 / 3057 行
```

---

## 2. 系统行为规律

**RULE-GOV-01:**
- condition: skill error_rate >= 0.3
- behavior: 自动降级至 DEPRECATED，排除出 best_skill_for 候选集
- observed effect: http (37.5% error) 被自动降级，不再被 router 选中

**RULE-GOV-02:**
- condition: skill success_rate > 0.85
- behavior: 从 EXPERIMENTAL 提升至 ACTIVE
- observed effect: llm 和 code 在 15+ 次成功后自动晋升

**RULE-GOV-03:**
- condition: skill error_rate >= 0.5
- behavior: 自动标记 REMOVED（不可恢复）
- observed effect: 目前无 skill 触发此条件

**RULE-INSIGHT-01:**
- condition: declining_skills > 0 OR conflicts > 0 OR drift_score > 0.1
- behavior: health_status = degraded
- observed effect: http 降级触发 degraded 状态

**RULE-INSIGHT-02:**
- condition: drift_detected OR (declining > 2 AND conflicts > 2)
- behavior: health_status = unstable
- observed effect: 当前无触发场景

**RULE-DRIFT-01:**
- condition: 首次 detect() 调用
- behavior: 建立本地 JSON 基线，返回 drift_detected = false
- observed effect: 第二次调用起才可检测变化

**RULE-SELECTION-01:**
- condition: action 匹配多个 skill keyword
- behavior: 取 combined_score 最高者，过滤 DEPRECATED/REMOVED
- observed effect: llm (score 0.998) > code (0.997) > http (0.697)

---

## 3. 可执行系统规则

```
RULE-LLM-SELECT-01:
  IF action matches "llm"|"ai"|"chat"|"问答"|"分析" THEN skill = llm
  EFFECT: 低延迟 0.15s, 评分 0.998

RULE-CODE-SELECT-01:
  IF action matches "代码"|"执行"|"python"|"脚本"|"编译"|"测试" THEN skill = code
  EFFECT: 中等延迟 0.30s, 评分 0.997

RULE-HTTP-SELECT-01:
  IF action matches "网络"|"请求"|"http"|"api"|"curl" THEN skill = http
  EFFECT: 高延迟 1.06s, 成功率 0.625, 已 DEPRECATED

RULE-GOV-DEMOTE-01:
  IF error_rate >= 0.3 AND status in (ACTIVE,STABLE,EXPERIMENTAL) THEN status = DEPRECATED
  EFFECT: skill 移出选择池

RULE-GOV-REMOVE-01:
  IF error_rate >= 0.5 THEN status = REMOVED
  EFFECT: 不可逆移除

RULE-GOV-PROMOTE-01:
  IF success_rate > 0.85 AND status = EXPERIMENTAL THEN status = ACTIVE
  EFFECT: skill 正式可用

RULE-GOV-PROMOTE-02:
  IF success_rate > 0.95 AND usage > 50 AND status = ACTIVE THEN status = STABLE
  EFFECT: skill 标记为稳定

RULE-INSIGHT-HEALTH-01:
  IF declining=0 AND conflicts=0 AND drift<=0.1 THEN health = "healthy"
  EFFECT: 无操作建议

RULE-INSIGHT-HEALTH-02:
  IF declining>0 OR conflicts>0 OR drift>0.1 THEN health = "degraded"
  EFFECT: 生成审查建议

RULE-INSIGHT-HEALTH-03:
  IF declining>2 OR conflicts>2 OR drift_detected THEN health = "unstable"
  EFFECT: 生成操作建议 + 漂移警告

RULE-DRIFT-BASELINE-01:
  IF first_call OR baseline_missing THEN save_baseline, drift = false
  EFFECT: 建立参照点

RULE-DRIFT-ERROR-01:
  IF error_rate_delta > 0.05 THEN drift_score += 0.2
  EFFECT: 错误率偏移量化

RULE-DRIFT-CONFLICT-01:
  IF conflicts_count_increased THEN drift_score += 0.25
  EFFECT: 功能重叠增加被标记

RULE-DRIFT-THRESHOLD-01:
  IF drift_score >= 0.3 THEN drift_detected = true
  EFFECT: 触发 unstable 健康状态
```

---

## 4. 系统问题与偏差分析

### Routing 偏差
```
  - http skill 因 timeout 降级后无替代 skill，HTTP 能力消失
  - 纯 keyword 匹配，无 context-aware 路由
  - 降级后无"替代路径"机制
```

### Skill 失效或滥用
```
  - http: 37.5% 失败率，3 次 timeout，已 DEPRECATED
      root cause: 无 timeout 限制或 retry
  - llm: 独占 56.6% 调用量，单点依赖风险
  - 无跨 skill fallback 链
```

### Token 浪费路径
```
  - governance 不追踪 token 消耗
  - code skill 每次调用包含完整代码内容
  - http fail 重试重复消耗
```

### LLM 过度使用场景
```
  - governance 不区分"真正需要 LLM" vs "可用规则替代"
  - 无 task_complexity 模型
```

### Fallback 触发频率
```
  - http: 3/8 = 37.5% → DEPRECATED
  - code: 0%, llm: 0%（测试中）
  - 系统无跨 skill fallback 链
```

---

## 5. 知识库写入块

```yaml
ZSK_VERSION: v1.86
TYPE: system_behavior_snapshot

INSIGHTS:
  - llm skill 独占 56.6% 调用量，无替代路径
  - http skill 因 timeout 自动降级，HTTP 能力消失
  - governance 自动升降级正常工作
  - insight drift detector 首次调用建立基线，第二次起生效
  - 系统 48 文件 / 3057 行，冻结层 361 行零改动

RULES:
  - name: RULE-GOV-DEMOTE-01
    condition: error_rate >= 0.3 AND status in (ACTIVE,STABLE,EXPERIMENTAL)
    action: status = DEPRECATED
  - name: RULE-GOV-REMOVE-01
    condition: error_rate >= 0.5
    action: status = REMOVED
  - name: RULE-GOV-PROMOTE-01
    condition: success_rate > 0.85 AND status = EXPERIMENTAL
    action: status = ACTIVE
  - name: RULE-INSIGHT-HEALTH-01
    condition: declining=0 AND conflicts=0 AND drift<=0.1
    action: health = "healthy"
  - name: RULE-INSIGHT-HEALTH-02
    condition: declining>0 OR conflicts>0 OR drift>0.1
    action: health = "degraded"
  - name: RULE-INSIGHT-HEALTH-03
    condition: declining>2 OR conflicts>2 OR drift_detected
    action: health = "unstable"
  - name: RULE-DRIFT-ERROR-01
    condition: error_rate_delta > 0.05
    action: drift_score += 0.2
  - name: RULE-DRIFT-CONFLICT-01
    condition: conflicts_count_increased
    action: drift_score += 0.25
  - name: RULE-DRIFT-THRESHOLD-01
    condition: drift_score >= 0.3
    action: drift_detected = true

METRICS:
  total_files: 48
  total_lines: 3057
  frozen_layer_lines: 361
  capability_layer_lines: 344
  governance_layer_lines: 416
  insight_layer_lines: 340
  tests: 133
  test_time_seconds: 1.42
  test_pass_rate: 1.0
  skills: 3
  skills_promoted_to_active: 2
  skills_deprecated: 1
  total_calls_simulated: 53
  overall_success_rate: 0.906

RISKS:
  - level: MEDIUM
    issue: http skill 降级后无替代
    impact: HTTP 能力不可用
  - level: LOW
    issue: llm 单点依赖 (56.6%)
    impact: llm 失效则系统无备用 LLM
  - level: LOW
    issue: 无跨 skill fallback 链
    impact: 单 skill 失败直接返回 error
  - level: LOW
    issue: governance 不追踪 token
    impact: 无法优化 cost
```

---

## 6. 版本变化分析（v1.85 → v1.86）

### 变化点
```
  - 新增 insight/ 目录（5 文件，340 行）
  - 无任何现有文件被修改
  - 冻结层 4 文件零改动
  - governance/ 只读不改
```

### 系统稳定性评估
```
  - 更稳定：Insight Agent 是纯观察层，不改变执行路径
  - 无新增控制路径：不参与 kernel/executor/router 决策
  - 无副作用：drift baseline 仅写入本地 JSON
```

### 结构漂移检查
```
  - 未发生结构偏移：冻结层零改动
  - governance + capability + insight 三层可观测生态完整
  - Kernel 唯一控制权未受影响
```
