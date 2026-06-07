# CLAUDE.md

Stock Agent - A股AI选股研究工具，基于DVexa框架改造。

## Architecture

```
app.py (Streamlit前端, 5页面)
  |
  +-- core/          控制循环 (kernel -> executor -> guard)
  +-- agents/        LLM策略规划器 (4种策略模板)
  +-- tools/         选股工具 (数据/财务/AI分析/筛选/对比)
  +-- governance/    治理层 (数据质量/效果追踪/分析评分/生命周期)
  +-- storage/       存储层 (SQLite/自选股/事件存储)
  +-- runtime/       运行时引擎 (事件溯源)
  +-- evaluation/    推荐效果评估
  +-- config/        配置管理
  +-- memory/        内存存储
```

## Commands

```bash
streamlit run app.py
python -m pytest tests/ -v
python -c "import core; import tools; import storage; import governance; print('OK')"
pip install -r requirements.txt
```

## Modules

- core/kernel.py - 主控制循环
- core/executor.py - 执行器 (screening/deep_analysis/comparison)
- core/guard.py - CBF过滤器
- agents/base_agent.py - LLM规划器 (value/growth/quality/comprehensive)
- tools/stock_data.py - akshare数据获取
- tools/financial.py - 五维度财务评分
- tools/analyst.py - AI分析 (单股/批量/对比)
- tools/screener.py - 条件筛选器
- tools/comparator.py - 行业对比
- governance/governance_kernel.py - 数据质量检查
- governance/feedback_engine.py - 推荐效果追踪
- governance/analysis_governor.py - 分析质量管控
- governance/analysis_score.py - 贝叶斯评分
- storage/database.py - SQLite存储
- storage/watchlist.py - 自选股管理
- storage/event_store.py - 事件存储 (JSONL)
