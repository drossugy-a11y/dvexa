# Stock Agent

A股AI选股研究工具。基于DVexa agent运行时框架改造。

## 功能

- **AI选股**: 设置筛选条件，AI从全市场挑选优质股票
- **个股详情**: 五维度评分 + AI深度分析 + 行业对比
- **股票对比**: 多只股票横向对比，雷达图叠加
- **自选股管理**: 标签分类、研究笔记
- **研究日志**: 完整事件流记录

## 评分体系

五维度财务评分 (各0-100分):
- 成长性: 营收增速、净利润增速、趋势
- 盈利能力: ROE、毛利率、持续性
- 估值: PE/PB分位数、PEG、股息率
- 财务健康: 资产负债率、流动比率、现金流
- 质量: 毛利率稳定性、ROE持续性

默认权重: 成长25% + 盈利25% + 估值20% + 健康15% + 质量15%

## 四种策略

- **价值型**: PE/PB/股息率/现金流
- **成长型**: 营收增速/利润增速/ROE趋势
- **质量型**: 毛利率/ROE/资产负债率/现金流质量
- **综合型**: 以上全部加权

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置
cp .env.example .env
# 编辑 .env 填入 LLM_API_KEY

# 3. 启动
streamlit run app.py
```

## 项目结构

```
stock-agent/
+-- core/           控制循环
+-- agents/         LLM规划器
+-- tools/          选股工具
+-- governance/     治理层
+-- storage/        存储层
+-- runtime/        运行时引擎
+-- evaluation/     效果评估
+-- config/         配置
+-- app.py          Streamlit前端
+-- requirements.txt
+-- .env.example
```

## 数据源

基于 [akshare](https://github.com/akfamily/akshare) 获取A股数据。

## 注意事项

- 实验性研究工具，不构成投资建议
- LLM分析结果仅供参考，需结合人工判断
- akshare接口有频率限制，数据缓存到SQLite
