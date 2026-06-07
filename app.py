"""Stock Agent — A 股 AI 选股研究工具

Streamlit 前端，5 个页面：
  1. AI 选股（首页）
  2. 个股详情
  3. 股票对比
  4. 自选股管理
  5. 研究日志
"""

import streamlit as st
import json
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.config import (
    LLM_API_KEY, LLM_BASE_URL, LLM_MODEL,
    DB_PATH, DEFAULT_STRATEGY,
)
from storage.database import StockDatabase
from storage.watchlist import Watchlist
from storage.event_store import StockEventStore
from tools.stock_data import StockDataTool
from tools.financial import FinancialAnalyzer
from tools.analyst import StockAnalyst
from tools.screener import StockScreener
from tools.comparator import IndustryComparator
from governance.governance_kernel import StockGovernanceKernel
from governance.feedback_engine import StockFeedbackEngine


# ── 初始化 ────────────────────────────────────────────────────────────────

@st.cache_resource
def init_tools():
    db = StockDatabase(DB_PATH)
    watchlist = Watchlist(DB_PATH)
    event_store = StockEventStore()
    stock_data = StockDataTool()
    financial = FinancialAnalyzer(stock_data)
    screener = StockScreener(stock_data, db)
    comparator = IndustryComparator(stock_data, financial)

    llm_tool = None
    if LLM_API_KEY:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)

            class LLMTool:
                def call(self, prompt, system_prompt=""):
                    resp = client.chat.completions.create(
                        model=LLM_MODEL,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt},
                        ],
                        temperature=0.3,
                    )
                    return {"content": resp.choices[0].message.content}

            llm_tool = LLMTool()
        except Exception:
            pass

    analyst = StockAnalyst(llm_tool) if llm_tool else None
    governance = StockGovernanceKernel()
    feedback = StockFeedbackEngine()

    return {
        "db": db, "watchlist": watchlist, "event_store": event_store,
        "stock_data": stock_data, "financial": financial,
        "analyst": analyst, "screener": screener, "comparator": comparator,
        "governance": governance, "feedback": feedback,
        "llm_available": llm_tool is not None,
    }


tools = init_tools()

# ── 侧边栏导航 ──────────────────────────────────────────────────────────

st.set_page_config(page_title="Stock Agent", page_icon="📈", layout="wide")
st.sidebar.title("📈 Stock Agent")
st.sidebar.caption("A 股 AI 选股研究工具")

page = st.sidebar.radio(
    "导航",
    ["🔍 AI 选股", "📊 个股详情", "⚖️ 股票对比", "⭐ 自选股管理", "📋 研究日志"],
)

if not tools["llm_available"]:
    st.sidebar.warning("⚠️ 未配置 LLM API Key，AI 分析功能不可用")
    st.sidebar.info("请在 .env 文件中设置 LLM_API_KEY")


# ════════════════════════════════════════════════════════════════════════
# 页面 1: AI 选股
# ════════════════════════════════════════════════════════════════════════

def page_screening():
    st.title("🔍 AI 选股")
    st.caption("设置筛选条件，AI 帮你从全市场中挑选优质股票")

    col1, col2 = st.columns([1, 3])

    with col1:
        st.subheader("筛选条件")
        strategy = st.selectbox("分析策略", ["comprehensive", "value", "growth", "quality"],
                                format_func=lambda x: {"comprehensive": "综合型", "value": "价值型",
                                                       "growth": "成长型", "quality": "质量型"}[x])
        industry = st.text_input("行业关键词", placeholder="如：消费、医药")
        pe_max = st.slider("PE 上限", 0, 200, 50)
        roe_min = st.slider("ROE 下限 (%)", 0, 50, 10)
        market_cap_min = st.number_input("最低市值（亿）", 0, 10000, 50)

    with col2:
        if st.button("🚀 开始 AI 选股", type="primary", use_container_width=True):
            with st.spinner("正在筛选和分析..."):
                conditions = {
                    "industry": industry if industry else None,
                    "pe_max": pe_max,
                    "roe_min": roe_min,
                    "market_cap_min": market_cap_min,
                }

                # 1. 条件验证
                validation = tools["governance"].validate_screening_conditions(conditions)
                if validation["warnings"]:
                    for w in validation["warnings"]:
                        st.warning(w)

                # 2. 筛选
                screen_result = tools["screener"].screen(conditions)
                codes = screen_result.get("codes", [])
                st.info(f"筛选出 {len(codes)} 只候选股票")

                if not codes:
                    st.warning("未找到符合条件的股票，请调整筛选条件")
                    return

                # 3. 逐只分析
                results = []
                progress = st.progress(0)
                for i, code in enumerate(codes[:10]):
                    progress.progress((i + 1) / min(len(codes), 10))
                    fin_data = tools["financial"].call({"action": "score", "stock_code": code})

                    # 数据质量检查
                    quality = tools["governance"].check_data_quality(fin_data)
                    if not quality["passed"]:
                        continue

                    if tools["analyst"]:
                        ai_result = tools["analyst"].analyze_stock(code, fin_data)
                        # 一致性检查
                        consistency = tools["governance"].check_analysis_consistency(fin_data, ai_result)
                        ai_result["consistency"] = consistency
                        results.append(ai_result)
                    else:
                        results.append({"stock_code": code, "scores": fin_data})

                progress.progress(1.0)
                tools["db"].save_screening(conditions, [r.get("stock_code", "") for r in results])

            # 4. 展示结果
            if results:
                st.subheader(f"📊 分析结果（{len(results)} 只）")
                for stock in results:
                    with st.container():
                        c1, c2, c3, c4 = st.columns([1, 3, 1, 1])
                        code = stock.get("stock_code", "")
                        c1.write(f"**{code}**")
                        c2.write(stock.get("summary", stock.get("investment_logic", "")))
                        score = stock.get("score", stock.get("scores", {}).get("composite_score", "-"))
                        c3.metric("AI评分", score)
                        action = stock.get("action", "")
                        c4.write(action)

                        if st.button(f"⭐ 加入自选", key=f"add_{code}"):
                            tools["watchlist"].add(code, tag="待观察")
                            st.success(f"已加入自选股")

                        st.divider()


# ════════════════════════════════════════════════════════════════════════
# 页面 2: 个股详情
# ════════════════════════════════════════════════════════════════════════

def page_stock_detail():
    st.title("📊 个股详情")
    stock_code = st.text_input("输入股票代码", placeholder="如：600519")

    if not stock_code:
        return

    with st.spinner("正在获取数据..."):
        info = tools["stock_data"].get_stock_info(stock_code)
        fin_data = tools["financial"].call({"action": "score", "stock_code": stock_code})

    # 基本信息
    st.subheader(f"{info.get('name', stock_code)} ({stock_code})")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("行业", info.get("industry", "-"))
    col2.metric("市值", info.get("market_cap", "-"))
    col3.metric("综合评分", fin_data.get("composite_score", "-"))
    col4.metric("上市日期", info.get("list_date", "-"))

    # 数据质量检查
    quality = tools["governance"].check_data_quality(fin_data)
    if quality["warnings"]:
        for w in quality["warnings"]:
            st.warning(w)

    # 五维度雷达图
    dims = fin_data.get("dimensions", {})
    if dims:
        st.subheader("五维度评分")
        import plotly.graph_objects as go
        categories = ["成长性", "盈利能力", "估值", "财务健康", "质量"]
        values = [dims.get("growth", 0), dims.get("profitability", 0),
                  dims.get("valuation", 0), dims.get("health", 0), dims.get("quality", 0)]
        values.append(values[0])
        categories.append(categories[0])

        fig = go.Figure(data=go.Scatterpolar(r=values, theta=categories, fill="toself"))
        fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
                          showlegend=False, height=400)
        st.plotly_chart(fig, use_container_width=True)

    # AI 分析
    if tools["analyst"] and tools["llm_available"]:
        st.subheader("🤖 AI 分析")
        if st.button("开始 AI 分析", key="analyze_btn"):
            with st.spinner("AI 正在分析..."):
                ai_result = tools["analyst"].analyze_stock(stock_code, fin_data)
                consistency = tools["governance"].check_analysis_consistency(fin_data, ai_result)

            col1, col2 = st.columns([2, 1])
            with col1:
                st.write(f"**总结：** {ai_result.get('summary', '')}")
                st.write(f"**投资逻辑：** {ai_result.get('investment_logic', '')}")
                st.write(f"**估值判断：** {ai_result.get('valuation_assessment', '')}")

                strengths = ai_result.get("strengths", [])
                if strengths:
                    st.write("**优势：**")
                    for s in strengths:
                        st.write(f"  ✅ {s}")

                risks = ai_result.get("risks", [])
                if risks:
                    st.write("**风险：**")
                    for r in risks:
                        st.write(f"  ⚠️ {r}")

            with col2:
                ai_score = ai_result.get("score", "-")
                st.metric("AI 评分", f"{ai_score}/10")
                st.metric("建议", ai_result.get("action", "-"))

                if not consistency["consistent"]:
                    st.warning("⚠️ 一致性检查发现问题：")
                    for c in consistency["conflicts"]:
                        st.write(f"  - {c}")

            tools["db"].save_analysis(stock_code, "comprehensive",
                                       ai_result.get("score", 0), ai_result)

    # 行业对比
    st.subheader("🏭 行业对比")
    peers = tools["comparator"].get_industry_ranking(stock_code)
    if peers.get("peers"):
        st.write(f"行业：{peers.get('industry', '-')}，同行业 {peers.get('peer_count', 0)} 家公司")
        for p in peers.get("peers", [])[:5]:
            st.write(f"  - {p.get('代码', '')} {p.get('名称', '')}")

    # 研究笔记
    st.subheader("📝 研究笔记")
    note = st.text_area("添加笔记", key="note_input")
    if st.button("保存笔记"):
        tools["watchlist"].add(stock_code, tag="已研究", note=note)
        st.success("笔记已保存")

    # 历史分析
    history = tools["db"].get_analysis_history(stock_code)
    if history:
        st.subheader("📜 分析历史")
        for h in history[:5]:
            with st.expander(f"{h.get('created_at', '')} - 评分 {h.get('score', '-')}"):
                st.json(h.get("conclusion", {}))


# ════════════════════════════════════════════════════════════════════════
# 页面 3: 股票对比
# ════════════════════════════════════════════════════════════════════════

def page_comparison():
    st.title("⚖️ 股票对比")
    codes_input = st.text_area("输入股票代码（每行一个，2-5只）",
                                placeholder="600519\n000858\n002304")

    if st.button("开始对比", type="primary"):
        codes = [c.strip() for c in codes_input.strip().split("\n") if c.strip()]
        if len(codes) < 2:
            st.warning("请输入至少 2 只股票")
            return
        if len(codes) > 5:
            st.warning("最多对比 5 只股票")
            return

        with st.spinner("正在对比分析..."):
            all_data = []
            for code in codes:
                info = tools["stock_data"].get_stock_info(code)
                scores = tools["financial"].call({"action": "score", "stock_code": code})
                all_data.append({"stock_code": code, "info": info, "scores": scores})

        # 并排表格
        st.subheader("📊 关键指标对比")
        import pandas as pd
        rows = []
        for d in all_data:
            info = d.get("info", {})
            scores = d.get("scores", {})
            dims = scores.get("dimensions", {})
            rows.append({
                "代码": d["stock_code"],
                "名称": info.get("name", ""),
                "行业": info.get("industry", ""),
                "综合评分": scores.get("composite_score", "-"),
                "成长性": dims.get("growth", "-"),
                "盈利能力": dims.get("profitability", "-"),
                "估值": dims.get("valuation", "-"),
                "财务健康": dims.get("health", "-"),
                "质量": dims.get("quality", "-"),
            })
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True)

        # 雷达图叠加
        import plotly.graph_objects as go
        categories = ["成长性", "盈利能力", "估值", "财务健康", "质量"]
        fig = go.Figure()
        for d in all_data:
            dims = d.get("scores", {}).get("dimensions", {})
            values = [dims.get("growth", 0), dims.get("profitability", 0),
                      dims.get("valuation", 0), dims.get("health", 0), dims.get("quality", 0)]
            values.append(values[0])
            cats = categories + [categories[0]]
            fig.add_trace(go.Scatterpolar(r=values, theta=cats, fill="toself",
                                          name=d["stock_code"]))
        fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
                          showlegend=True, height=500)
        st.plotly_chart(fig, use_container_width=True)

        # AI 对比分析
        if tools["analyst"] and tools["llm_available"]:
            st.subheader("🤖 AI 对比分析")
            if st.button("开始 AI 对比"):
                with st.spinner("AI 正在对比分析..."):
                    result = tools["analyst"].compare_stocks(all_data)
                st.write(result.get("recommendation", ""))


# ════════════════════════════════════════════════════════════════════════
# 页面 4: 自选股管理
# ════════════════════════════════════════════════════════════════════════

def page_watchlist():
    st.title("⭐ 自选股管理")

    tag_filter = st.selectbox("按标签筛选", ["全部", "已研究", "待观察", "放弃"])
    tag = None if tag_filter == "全部" else tag_filter
    stocks = tools["watchlist"].list_all(tag)

    if not stocks:
        st.info("暂无自选股")
        add_code = st.text_input("添加自选股代码")
        if st.button("添加") and add_code:
            tools["watchlist"].add(add_code)
            st.rerun()
        return

    for stock in stocks:
        code = stock["code"]
        with st.container():
            col1, col2, col3, col4, col5 = st.columns([1, 1, 1, 2, 1])
            col1.write(f"**{code}**")
            col2.write(stock.get("tag", ""))

            new_tag = col3.selectbox("标签", ["已研究", "待观察", "放弃"],
                                      index=["已研究", "待观察", "放弃"].index(stock.get("tag", "待观察")),
                                      key=f"tag_{code}", label_visibility="collapsed")
            if new_tag != stock.get("tag"):
                tools["watchlist"].update_tag(code, new_tag)

            note = stock.get("note", "")
            col4.write(note[:50] + "..." if len(note) > 50 else note)

            if col5.button("❌", key=f"rm_{code}"):
                tools["watchlist"].remove(code)
                st.rerun()

            st.divider()

    # 添加新股票
    st.subheader("添加自选股")
    add_code = st.text_input("股票代码", key="add_watchlist")
    add_tag = st.selectbox("标签", ["待观察", "已研究", "放弃"], key="add_tag")
    add_note = st.text_input("备注", key="add_note")
    if st.button("添加到自选"):
        if add_code:
            tools["watchlist"].add(add_code, tag=add_tag, note=add_note)
            st.success(f"已添加 {add_code}")
            st.rerun()


# ════════════════════════════════════════════════════════════════════════
# 页面 5: 研究日志
# ════════════════════════════════════════════════════════════════════════

def page_research_log():
    st.title("📋 研究日志")

    col1, col2 = st.columns(2)
    filter_type = col1.selectbox("事件类型", ["全部", "analysis", "data_fetch", "screening", "user_action"])
    filter_code = col2.text_input("按股票代码筛选")

    events = tools["event_store"].get_recent(100)
    if filter_type != "全部":
        events = [e for e in events if e.get("event_type") == filter_type]
    if filter_code:
        events = [e for e in events if e.get("stock_code") == filter_code]

    if not events:
        st.info("暂无研究日志")
        return

    for event in reversed(events):
        with st.expander(
            f"{event.get('timestamp', '')[:19]} | "
            f"{event.get('event_type', '')} | "
            f"{event.get('stock_code', '-')}"
        ):
            st.json(event.get("data", {}))


# ════════════════════════════════════════════════════════════════════════
# 路由
# ════════════════════════════════════════════════════════════════════════

if page == "🔍 AI 选股":
    page_screening()
elif page == "📊 个股详情":
    page_stock_detail()
elif page == "⚖️ 股票对比":
    page_comparison()
elif page == "⭐ 自选股管理":
    page_watchlist()
elif page == "📋 研究日志":
    page_research_log()
