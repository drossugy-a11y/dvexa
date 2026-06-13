/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { Stock, ResearchLog } from '../types';

export const ALL_STOCKS: Stock[] = [
  {
    id: 'NVDA',
    name: 'NVIDIA Corp.',
    nameZh: '英伟达',
    sector: 'AI Semiconductor',
    price: 875.28,
    changePercent: 2.45,
    changeAmount: 20.93,
    volume: '45.2M',
    marketCap: '$2.15T',
    peRatio: 72.4,
    beta: 1.68,
    aiScore: 92,
    ratingType: 'Strong Buy',
    factors: {
      '动量': 98,
      '成长': 95,
      '质量': 88,
      '估值': 35,
      '波动': 60
    },
    aiAnalysis: {
      catalysts: '数据中心收入连续三个季度超预期，Hopper架构GPU需求持续强劲。供应链数据显示，产能瓶颈正在缓解，预计下季度毛利率将维持在75%以上的高位。',
      trendLogic: '动量因子评分达到第99百分位。量化模型检测到机构资金持续净流入，且空头头寸降至历史低点。价格突破关键阻力位$850，形成看涨上升通道。',
      riskAlerts: '当前市盈率(PE)显著高于历史平均水平，估值因子极低。宏观层面上，若美联储推迟降息，高成长科技股可能面临短期估值重估的压力。',
      action: '建议采用期权领口策略(Collar Strategy)锁定部分利润，同时保留上行参与度。逢回调至$820-$830区间可考虑加仓。'
    },
    historyTrend: [
      { label: 'Oct', score: 70 },
      { label: 'Nov', score: 72 },
      { label: 'Dec', score: 80 },
      { label: 'Jan', score: 88 },
      { label: 'Feb', score: 85 },
      { label: 'Mar', score: 92 }
    ],
    peers: [
      { ticker: 'NVDA', name: '英伟达', score: 92, pe: '72.4', growth: '+125%', trend: 'up' },
      { ticker: 'AMD', name: '超微半导体', score: 78, pe: '315.2', growth: '+45%', trend: 'up' },
      { ticker: 'INTC', name: '英特尔', score: 45, pe: 'N/A', growth: '-12%', trend: 'down' },
      { ticker: 'TSM', name: '台积电', score: 85, pe: '22.8', growth: '+15%', trend: 'up' }
    ],
    financials: {
      peForecast: '34.2x',
      growthYoY: '125.8%',
      margin: '75.2%',
      debtRatio: '0.32',
      alpha1Y: '1.45'
    },
    sparkline: [25, 20, 22, 10, 15, 5]
  },
  {
    id: 'TSLA',
    name: 'Tesla Inc.',
    nameZh: '特斯拉',
    sector: 'Electric Vehicles',
    price: 177.46,
    changePercent: -1.15,
    changeAmount: -2.05,
    volume: '81.4M',
    marketCap: '$564B',
    peRatio: 56.5,
    beta: 1.42,
    aiScore: 65,
    ratingType: 'Hold',
    factors: {
      '动量': 45,
      '成长': 55,
      '质量': 70,
      '估值': 30,
      '波动': 85
    },
    aiAnalysis: {
      catalysts: '近期交付量面临阶段性瓶颈，第一季度全球交付相比去年同期有所下降，自动驾驶FSD订阅降价以刺激需求，新车型发布时间表加速推进，成为潜在催化剂。',
      trendLogic: '由于动量因子回撤，模型检测到资金流入趋缓。价格处于探底筑底阶段，短期受到日线阻力压制，处于下行震荡区间中。',
      riskAlerts: '利润率面临进一步下滑压力，市场竞争激烈，宏观利率处于高位打压大众买车意愿，估值溢价需要自动驾驶(Robotaxi)进展有力支撑。',
      action: '当前估值具备一定边际安全，可开展小仓位定投。技术面上若站上$190可考虑突破加仓，目前建议以防御性的期权卖出(Short Put)策略收租为主。'
    },
    historyTrend: [
      { label: 'Oct', score: 82 },
      { label: 'Nov', score: 78 },
      { label: 'Dec', score: 75 },
      { label: 'Jan', score: 68 },
      { label: 'Feb', score: 64 },
      { label: 'Mar', score: 65 }
    ],
    peers: [
      { ticker: 'NVDA', name: '英伟达', score: 92, pe: '72.4', growth: '+125%', trend: 'up' },
      { ticker: 'TSLA', name: '特斯拉', score: 65, pe: '65.8', growth: '+18.5%', trend: 'up' },
      { ticker: 'AMD', name: '超微半导体', score: 78, pe: '315.2', growth: '+45%', trend: 'up' },
      { ticker: 'TSM', name: '台积电', score: 85, pe: '22.8', growth: '+15%', trend: 'up' }
    ],
    financials: {
      peForecast: '65.8x',
      growthYoY: '18.5%',
      margin: '18.2%',
      debtRatio: '0.15',
      alpha1Y: '-0.22'
    },
    sparkline: [15, 22, 18, 25, 20, 24]
  },
  {
    id: 'AMD',
    name: 'Advanced Micro Devices',
    nameZh: '超微半导体',
    sector: 'AI Semiconductor',
    price: 160.20,
    changePercent: 1.82,
    changeAmount: 2.86,
    volume: '52.0M',
    marketCap: '$258B',
    peRatio: 315.2,
    beta: 1.76,
    aiScore: 78,
    ratingType: 'Buy',
    factors: {
      '动量': 80,
      '成长': 78,
      '质量': 65,
      '估值': 25,
      '波动': 72
    },
    aiAnalysis: {
      catalysts: 'MI300X 系列AI加速器出货顺畅，销售额指引不断被上调。公司在服务器CPU领域的份额保持稳步扩张势头。AIPC换机潮有望在下半年注入额外业务动能。',
      trendLogic: '机构净持仓处于中高位水平。股价处于关键颈线位支撑上方进行健康的震荡整固，均线多头排列趋势完好。',
      riskAlerts: '市盈率(PE)倍数高企，导致容错空间极小。竞争对手NVIDIA的产品迭代效率给AMD带来极定制化的竞争压力，市场流动性收紧可能带来溢价折算风险。',
      action: '利用波动进行区间网格套利，建仓成本可设在$145-$150水平。中长期关注MI400系列路线图进展。'
    },
    historyTrend: [
      { label: 'Oct', score: 65 },
      { label: 'Nov', score: 70 },
      { label: 'Dec', score: 72 },
      { label: 'Jan', score: 75 },
      { label: 'Feb', score: 78 },
      { label: 'Mar', score: 78 }
    ],
    peers: [
      { ticker: 'NVDA', name: '英伟达', score: 92, pe: '72.4', growth: '+125%', trend: 'up' },
      { ticker: 'AMD', name: '超微半导体', score: 78, pe: '315.2', growth: '+45%', trend: 'up' },
      { ticker: 'INTC', name: '英特尔', score: 45, pe: 'N/A', growth: '-12%', trend: 'down' },
      { ticker: 'TSM', name: '台积电', score: 85, pe: '22.8', growth: '+15%', trend: 'up' }
    ],
    financials: {
      peForecast: '42.1x',
      growthYoY: '4.2%',
      margin: '46.5%',
      debtRatio: '0.18',
      alpha1Y: '0.85'
    },
    sparkline: [10, 15, 12, 18, 14, 20]
  },
  {
    id: 'TSM',
    name: 'Taiwan Semiconductor',
    nameZh: '台积电',
    sector: 'AI Semiconductor',
    price: 142.50,
    changePercent: 3.12,
    changeAmount: 4.31,
    volume: '15.6M',
    marketCap: '$738B',
    peRatio: 22.8,
    beta: 1.15,
    aiScore: 85,
    ratingType: 'Buy',
    factors: {
      '动量': 85,
      '成长': 72,
      '质量': 92,
      '估值': 60,
      '波动': 40
    },
    aiAnalysis: {
      catalysts: '先进封装CoWoS产能极度紧缺，台积电计划将产能翻倍依然未能完全满足头部大客户订单需求。3纳米（N3）制程工艺产能保持全负荷生产，具备无可匹敌的议价权。',
      trendLogic: '由于极高的业务护城河，长期资金持续流入。技术面上股价跳空突破中枢，形成强有力的中长线上升趋势，回撤支撑显着。',
      riskAlerts: '地缘政治冲突溢价是其核心拖累因子。海外建厂（如美国和德国）高昂的基建与运维成本可能在短期内压低整体毛利水平。',
      action: '极佳的中长底仓标的，合理分批买入持有。股价如若回调探至100日均线即是良好加仓胜率极高的买点。'
    },
    historyTrend: [
      { label: 'Oct', score: 75 },
      { label: 'Nov', score: 78 },
      { label: 'Dec', score: 79 },
      { label: 'Jan', score: 82 },
      { label: 'Feb', score: 84 },
      { label: 'Mar', score: 85 }
    ],
    peers: [
      { ticker: 'NVDA', name: '英伟达', score: 92, pe: '72.4', growth: '+125%', trend: 'up' },
      { ticker: 'TSM', name: '台积电', score: 85, pe: '22.8', growth: '+15%', trend: 'up' },
      { ticker: 'AMD', name: '超微半导体', score: 78, pe: '315.2', growth: '+45%', trend: 'up' },
      { ticker: 'INTC', name: '英特尔', score: 45, pe: 'N/A', growth: '-12%', trend: 'down' }
    ],
    financials: {
      peForecast: '22.8x',
      growthYoY: '15.0%',
      margin: '51.3%',
      debtRatio: '0.22',
      alpha1Y: '0.54'
    },
    sparkline: [8, 12, 11, 16, 15, 22]
  },
  {
    id: 'MSFT',
    name: 'Microsoft Corp.',
    nameZh: '微软',
    sector: 'Cloud & AI Software',
    price: 421.90,
    changePercent: 0.85,
    changeAmount: 3.56,
    volume: '22.4M',
    marketCap: '$3.13T',
    peRatio: 36.8,
    beta: 0.90,
    aiScore: 95,
    ratingType: 'Strong Buy',
    factors: {
      '动量': 88,
      '成长': 82,
      '质量': 96,
      '估值': 40,
      '波动': 30
    },
    aiAnalysis: {
      catalysts: 'Azure 云服务在AI算力赋能下增速远超同业客户（AWS/GCP）。Copilot 办公软件商业化订阅用户大增，企业级AI服务需求正快速释放成坚实盈余。',
      trendLogic: '高权重防御型万亿级市值科技核心。大资产包底仓标的，筹码极牢固，动量平滑向上，机构对优质盈利现金流情有独钟。',
      riskAlerts: '估值处于过去十年均线偏高分位。AI数据中心等资本开支大幅抬高，可能挤压短期自由现金流收益。',
      action: '适合大仓位被动配置，推荐采取备兑看涨期权(Covered Call)增厚整体收益率，锁定复合成长复利。'
    },
    historyTrend: [
      { label: 'Oct', score: 90 },
      { label: 'Nov', score: 92 },
      { label: 'Dec', score: 91 },
      { label: 'Jan', score: 93 },
      { label: 'Feb', score: 94 },
      { label: 'Mar', score: 95 }
    ],
    peers: [
      { ticker: 'MSFT', name: '微软', score: 95, pe: '31.2', growth: '+16%', trend: 'up' },
      { ticker: 'GOOGL', name: '谷歌', score: 83, pe: '22.5', growth: '+14%', trend: 'up' },
      { ticker: 'AAPL', name: '苹果', score: 72, pe: '26.8', growth: '+2%', trend: 'down' },
      { ticker: 'AMZN', name: '亚马逊', score: 88, pe: '38.4', growth: '+12%', trend: 'up' }
    ],
    financials: {
      peForecast: '31.2x',
      growthYoY: '16.0%',
      margin: '43.5%',
      debtRatio: '0.28',
      alpha1Y: '0.38'
    },
    sparkline: [20, 18, 15, 18, 10, 8]
  },
  {
    id: 'INTC',
    name: 'Intel Corp.',
    nameZh: '英特尔',
    sector: 'Semiconductors',
    price: 30.45,
    changePercent: -2.10,
    changeAmount: -0.65,
    volume: '38.5M',
    marketCap: '$128B',
    peRatio: null,
    beta: 1.20,
    aiScore: 45,
    ratingType: 'Reduce',
    factors: {
      '动量': 25,
      '成长': 15,
      '质量': 40,
      '估值': 78,
      '波动': 55
    },
    aiAnalysis: {
      catalysts: '代工服务(IFS)仍处于巨额投资的资本流出阶段，18A先进制程的投产情况是公司逆袭的唯一胜率。剥离子公司（如Altera）能有效补血财务亏损。',
      trendLogic: '资金净流出，空头头寸居高不下。技术面处于明显的破位下探过程，多条移动平均线死叉向下压制，亟需业绩验证拐点。',
      riskAlerts: '服务器CPU传统优势市场持续流失给新型AI算力。自由现金流处于赤字红区，沉重的代工前期资产计提或造成亏损超市场预期。',
      action: '建议观望，等待下半年IFS商用客户合作及良率等先决转折数据落地，反转前切勿底部抄底。'
    },
    historyTrend: [
      { label: 'Oct', score: 55 },
      { label: 'Nov', score: 52 },
      { label: 'Dec', score: 50 },
      { label: 'Jan', score: 48 },
      { label: 'Feb', score: 46 },
      { label: 'Mar', score: 45 }
    ],
    peers: [
      { ticker: 'NVDA', name: '英伟达', score: 92, pe: '72.4', growth: '+125%', trend: 'up' },
      { ticker: 'AMD', name: '超微半导体', score: 78, pe: '315.2', growth: '+45%', trend: 'up' },
      { ticker: 'INTC', name: '英特尔', score: 45, pe: 'N/A', growth: '-12%', trend: 'down' },
      { ticker: 'TSM', name: '台积电', score: 85, pe: '22.8', growth: '+15%', trend: 'up' }
    ],
    financials: {
      peForecast: '24.5x',
      growthYoY: '-12.0%',
      margin: '38.2%',
      debtRatio: '0.45',
      alpha1Y: '-0.48'
    },
    sparkline: [30, 28, 35, 32, 40, 48]
  }
];

export const RESEARCH_LOGS: ResearchLog[] = [
  {
    id: 'log-1',
    date: '2023-10-24',
    avgScore: 92.4,
    tickers: ['NVDA', 'AMD', 'PLTR'],
    summary: '强烈的算力资本支出预期推动半导体板块动量聚集。模型识别到非结构化数据中提及“供应链紧缺”的频率激增，多因子评分模型中【动量】与【情绪】因子达到极值。',
    outputText: {
      analysis: '检测到行业板块动量异常。半导体硬件设备制造分支展现出极强的做多信号 (Strength: 0.94)。',
      catalyst: '核心驱动因子源自财报前期的供应链备货数据激增，以及期权市场隐含波动率倾斜 (IV Skew) 暗示的机构抢筹行为。',
      decision: '建议超配高Beta算力核心标的，对冲宏观下行风险。'
    },
    factors: {
      '动量': 96,
      '情绪': 94,
      '成长': 88,
      '质量': 85,
      '估值': 32
    },
    corePool: [
      { ticker: 'NVDA', score: 98, returnT5: 12.4, isPositive: true },
      { ticker: 'AMD', score: 89, returnT5: 7.8, isPositive: true },
      { ticker: 'PLTR', score: 85, returnT5: 5.1, isPositive: true }
    ]
  },
  {
    id: 'log-2',
    date: '2023-10-23',
    avgScore: 85.1,
    tickers: ['META', 'GOOGL'],
    summary: '大盘缩量震荡，AI倾向于防御性增长股。广告收入预期边际改善，财务健康因子占优，资本结构强劲。',
    outputText: {
      analysis: '大盘宏观指数在多条阻力均线处徘徊，波动率（VIX）探底回升，多因子框架主动调低超高Beta科技股权重，避风港情绪转浓。',
      catalyst: '数字营销及线上广告头部双寡头显露出了扎实的运营利润率控制力且具备充盈的自由现金流安全垫。',
      decision: '配置防守成长大底仓（META, GOOGL），对冲科技大市短期溢价整固修正。'
    },
    factors: {
      '动量': 82,
      '情绪': 78,
      '成长': 85,
      '质量': 90,
      '估值': 45
    },
    corePool: [
      { ticker: 'META', score: 88, returnT5: 4.2, isPositive: true },
      { ticker: 'GOOGL', score: 82, returnT5: 3.1, isPositive: true }
    ]
  },
  {
    id: 'log-3',
    date: '2023-10-20',
    avgScore: 41.2,
    tickers: ['CASH'],
    summary: '宏观不确定性增加，系统性风险预警触发。多项量化指标转负，模型建议降低仓位，积极持有现金资产防范风险。',
    outputText: {
      analysis: '宏观流动性指标快速收缩，美债10年期收益率突破前高，美联储鹰派声明增加市场不确定性，高估值科技股估值重构承压。',
      catalyst: '地缘政治冲突陡然升级叠加宏观加息周期延长双重叠加，资金开始出现明显的避险撤出动作。',
      decision: '仓位控制从先前的超配降至低配防守，部分盈利头寸止盈结清，防守配置现金与国债。'
    },
    factors: {
      '动量': 22,
      '情绪': 18,
      '成长': 35,
      '质量': 50,
      '估值': 75
    },
    corePool: [
      { ticker: 'CASH', score: 95, returnT5: 0.1, isPositive: true },
      { ticker: 'BIL(国债)', score: 90, returnT5: 0.08, isPositive: true }
    ]
  }
];
