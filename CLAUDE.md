# CLAUDE.md

DVexa v1.0 — A股AI量化选股系统（Clean Architecture）

## 项目架构

```
dvexa/
├── core/                      # 核心引擎
│   ├── engine/                # 主控制循环
│   │   └── kernel.py
│   ├── scheduler/             # 任务调度
│   │   └── trigger.py
│   └── memory/                # 上下文记忆
│       └── context.py
│
├── agents/                    # AI Agent 层
│   ├── research/              # 研究分析
│   │   ├── analyzer.py        # 深度分析
│   │   └── report.py          # 研究报告生成
│   ├── trading/               # 交易信号（Phase 2）
│   │   └── signal.py
│   └── analysis/              # 因子计算
│       └── factor_calc.py
│
├── strategies/                # 策略层（混合式）
│   ├── regime/                # 市场状态判断
│   │   ├── detector.py        # 牛/熊/震荡识别
│   │   └── switcher.py        # 策略自动切换
│   ├── configs/               # 策略配置（YAML）
│   │   ├── aggressive.yaml    # 牛市
│   │   ├── balanced.yaml      # 震荡市
│   │   └── defensive.yaml     # 熊市
│   ├── momentum/              # 动量策略
│   ├── mean_reversion/        # 均值回归策略
│   └── engine.py              # 策略执行引擎
│
├── data/                      # 数据层
│   ├── market/                # 市场数据
│   │   ├── akshare_feed.py    # akshare A股
│   │   └── cache.py           # SQLite 缓存
│   └── news/                  # 新闻（Phase 2）
│
├── interfaces/                # 接口层
│   ├── api/                   # REST API
│   │   └── server.py          # FastAPI
│   ├── streamlit/             # Streamlit UI（可选）
│   └── cli/                   # 命令行
│       └── main.py
│
├── web/                       # React 前端（DENG-main）
├── DENG的知识库/               # Obsidian 知识库
│
├── config/                    # 配置
│   ├── settings.py            # 全局配置
│   └── weights.py             # 因子权重
│
├── start.bat                  # Windows 一键启动
├── stop.bat                   # 停止服务
├── requirements.txt
├── CLAUDE.md
└── README.md
```

## 启动方式

```bash
# 一键启动（推荐）
双击 start.bat

# 手动启动
uvicorn interfaces.api.server:app --port 8000
cd web && npm run dev
```

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| GET | `/api/stocks?top_n=10` | Top N 股票列表 |
| GET | `/api/stocks/{code}` | 单股详情 + 研究报告 |
| POST | `/api/analyze` | 运行完整分析 |

## 核心流程

```
触发 → 市场状态判断 → 加载策略 → 数据获取 → 因子计算 → 策略筛选 → AI分析 → 研究报告
```

## 技术栈

- **后端**: Python 3.10+ / FastAPI / akshare / SQLite
- **前端**: React 19 / TypeScript / Vite / Tailwind CSS
- **知识库**: Obsidian（Markdown 笔记）
