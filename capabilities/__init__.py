"""Capability Layer — DVexa v1.7 能力增长隔离架构

定位：
  所有"变强"的东西全部丢这里。
  可以无限变大，但不能影响控制流。

约束：
  ✗ 不参与 planner 决策
  ✗ 不参与 executor 逻辑
  ✗ 不参与 kernel 判断
  ✔ 提供工具、执行能力、IO 扩展
"""
