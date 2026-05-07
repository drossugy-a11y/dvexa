# DVexa 系统架构文档

> **目录**: `ZSK/JGSJ/`（架构知识库）
> **说明**: 系统架构的完整中文文档，涵盖所有核心模块和设计决策。
> **同步版本**: v2.0

---

## 文件列表

| 文件 | 内容 | 页数 |
|------|------|------|
| [00_系统架构总览.md](00_系统架构总览.md) | 四层架构、6 阶段流水线、Event 数据结构、模块依赖、系统健康 | 全局 |
| [01_事件溯源运行时.md](01_事件溯源运行时.md) | Event/EventStore、Engine、RuntimeContext、Replay、Trace | 运行时层 |
| [02_能力图谱投影层.md](02_能力图谱投影层.md) | CapabilityGraph 数据模型、构建、查询、导出 | 投影层 |
| [03_治理层组件.md](03_治理层组件.md) | SGL、ATS、Scheduler、SkillGovernor、ToolPolicy、Event Transformer | 治理层 |
| [04_能力编译器.md](04_能力编译器.md) | Capability Compiler v1.0 设计规范（草案） | 编译层 |
| [05_v2架构转型.md](05_v2架构转型.md) | v2.0 Compiler-Driven Execution 架构转型规范 | 架构转型 |
| [06_compiler_v2核心.md](06_compiler_v2核心.md) | Compiler v2.0 8 阶段流水线、7 模块、113 测试 | 编译层 ✅ |

---

## 相关文档

- **版本规范**: [`ZSK/specs/`](../specs/)（SGL_v1.0, ATS_v1.2, ASSIMILATION_SCHEDULER_v1.0, DVX_v0.1, CAPABILITY_GRAPH_v1.0, COMPILER_V2_v1.0）
- **系统快照**: [`ZSK/XTKZ/`](../XTKZ/)（v1.89, v1.90, v1.91, v2.0）
- **里程碑**: [`ZSK/milestones/`](../milestones/)（ZT1-ZT11）
- **CLAUDE.md**: [`CLAUDE.md`](../../CLAUDE.md)（代码仓库指南）

---

*由 DVexa 系统维护 — 只读架构文档。*
