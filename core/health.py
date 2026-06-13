"""健康检查"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def check_health() -> dict:
    """检查系统各模块状态

    Returns:
        {
            'status': 'ok' | 'degraded' | 'error',
            'modules': {
                'env': {'status': 'ok', 'detail': '...'},
                'trading_agents': {'status': 'ok', 'detail': '...'},
                'akshare': {'status': 'ok', 'detail': '...'},
                'llm': {'status': 'ok', 'detail': '...'},
                'database': {'status': 'ok', 'detail': '...'},
            },
        }
    """
    modules = {}
    errors = 0

    # 1. .env 配置
    try:
        from config.settings import LLM_API_KEY, LLM_PROVIDER
        if LLM_API_KEY:
            modules['env'] = {'status': 'ok', 'detail': f'provider={LLM_PROVIDER}'}
        else:
            modules['env'] = {'status': 'warning', 'detail': 'LLM_API_KEY 未配置'}
            errors += 1
    except Exception as e:
        modules['env'] = {'status': 'error', 'detail': str(e)}
        errors += 1

    # 2. TradingAgents-CN
    try:
        from integrations import TradingAgentsWrapper
        wrapper = TradingAgentsWrapper()
        if wrapper.is_available():
            modules['trading_agents'] = {'status': 'ok', 'detail': '已加载'}
        else:
            modules['trading_agents'] = {'status': 'warning', 'detail': '未安装（降级模式）'}
    except Exception as e:
        modules['trading_agents'] = {'status': 'error', 'detail': str(e)}
        errors += 1

    # 3. akshare
    try:
        import akshare
        modules['akshare'] = {'status': 'ok', 'detail': f'v{akshare.__version__}'}
    except ImportError:
        modules['akshare'] = {'status': 'error', 'detail': '未安装'}
        errors += 1

    # 4. LLM 连通性
    try:
        from config.settings import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
        if LLM_API_KEY:
            from openai import OpenAI
            client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
            # 简单测试（不实际调用，只检查配置）
            modules['llm'] = {'status': 'ok', 'detail': f'{LLM_MODEL} @ {LLM_BASE_URL}'}
        else:
            modules['llm'] = {'status': 'warning', 'detail': 'API key 未配置'}
            errors += 1
    except Exception as e:
        modules['llm'] = {'status': 'error', 'detail': str(e)}
        errors += 1

    # 5. 数据库
    try:
        from core.memory.store import AnalysisMemory
        mem = AnalysisMemory()
        modules['database'] = {'status': 'ok', 'detail': 'SQLite 连接正常'}
    except Exception as e:
        modules['database'] = {'status': 'error', 'detail': str(e)}
        errors += 1

    # 总体状态
    if errors == 0:
        status = 'ok'
    elif errors <= 2:
        status = 'degraded'
    else:
        status = 'error'

    return {
        'status': status,
        'modules': modules,
    }
