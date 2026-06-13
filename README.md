# Stock Radar

A股AI选股研究终端 — 真实数据 + 五维评分 + AI解释 + 专业级UI。

![Architecture](https://img.shields.io/badge/FastAPI-Python-green) ![React](https://img.shields.io/badge/React-19-blue) ![Vite](https://img.shields.io/badge/Vite-6-purple)

## 一键启动

```bash
# Windows: 双击 start.bat
# 自动完成后端 + 前端 + 浏览器启动
# 停止服务: 双击 stop.bat
```

## 系统架构

```
┌─────────────────────┐        ┌─────────────────────┐
│   DENG-main (React) │  API   │  stock_radar (Python)│
│   localhost:3000     │◄──────►│  localhost:8000      │
│                     │        │                     │
│  • 奢华暗金UI        │        │  • akshare 真实数据   │
│  • AI评分排行榜      │        │  • 五维评分系统       │
│  • 五维雷达图        │        │  • ST/流动性筛选      │
│  • 多股对比矩阵      │        │  • LLM 解释引擎      │
│  • 模拟组合交易      │        │  • SQLite 缓存       │
└─────────────────────┘        └─────────────────────┘
```

## 功能特性

- **AI 评分榜**: 全市场 Top N 股票，按五维评分排序
- **个股详情**: 雷达图 + 核心指标 + AI深度分析
- **多股对比**: 因子叠加图 + 量化分析矩阵
- **研究日志**: 历史分析记录，T+5 收益追踪
- **模拟交易**: 虚拟资金买卖，持仓管理

## 评分体系

五维度财务评分（各0-100分）：

| 维度 | 权重 | 核心指标 |
|------|------|----------|
| 成长性 | 25% | 营收增长率、净利润增长率、趋势 |
| 盈利能力 | 25% | ROE、毛利率、持续性 |
| 估值 | 20% | PE/PB 区间评分 |
| 财务健康 | 15% | 资产负债率、流动比率、现金流 |
| 质量 | 15% | 毛利率稳定性、ROE 持续性 |

## 快速开始

### 方式一：一键启动（推荐）

```bash
# 双击 start.bat 即可
# 首次运行会自动安装依赖（约2-3分钟）
```

### 方式二：手动启动

```bash
# 终端1：启动后端
cd stock_radar
pip install -r requirements.txt
cp .env.example .env   # 编辑填入 LLM_API_KEY
uvicorn api:app --port 8000

# 终端2：启动前端
cd DENG-main
npm install
npm run dev

# 浏览器打开 http://localhost:3000
```

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| GET | `/api/stocks?top_n=10&pe_max=100` | Top N 股票列表 |
| GET | `/api/stocks/{code}` | 单股详情 + AI解释 |
| POST | `/api/analyze` | 运行新分析 |

## 项目结构

```
DvexaBFK-main/
├── start.bat              # Windows 一键启动
├── stop.bat               # 停止服务
├── stock_radar/           # Python 后端
│   ├── api.py             # FastAPI REST API
│   ├── data.py            # akshare 数据层
│   ├── scorer.py          # 五维评分
│   ├── selector.py        # 筛选器
│   ├── ai_explainer.py    # AI 解释
│   └── config.py          # 配置
├── DENG-main/             # React 前端
│   ├── src/               # 源码
│   └── package.json
└── DENG的知识库/           # Obsidian 知识库
```

## 数据源

基于 [akshare](https://github.com/akfamily/akshare) 获取A股实时数据，SQLite 本地缓存避免重复请求。

## 注意事项

- 实验性研究工具，不构成投资建议
- AI 仅提供解释分析，不参与选股决策
- akshare 接口有频率限制，已内置 0.5s 限流 + 缓存
- 前端 API 不可用时自动降级到本地示例数据

## 许可证

MIT License
