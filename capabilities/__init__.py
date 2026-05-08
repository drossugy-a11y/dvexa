"""Capability Layer — DVexa v1.7 能力增长隔离架构

定位：
  所有"变强"的东西全部丢这里。
  可以无限变大，但不能影响控制流。

约束：
  ✗ 不参与 planner 决策
  ✗ 不参与 executor 逻辑
  ✗ 不参与 kernel 判断
  ✔ 提供工具、执行能力、IO 扩展

v1.9 — Capability Taxonomy System:
  taxonomy.py         — 能力分类学核心模型 (CapabilityNode, MaturityLevel, TAXONOMY_TREE)
  capability_graph.py — 能力依赖/冲突图 (DAG, 环检测, 文本可视化)
  capability_registry.py — 统一能力注册中心
  evolution_tracker.py   — 能力演化追踪 (append-only)
"""
