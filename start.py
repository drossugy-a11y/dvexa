"""DVexa v1.0 一键启动器"""

import subprocess
import sys
import os
import time
import webbrowser
import socket

# Fix Windows console encoding
if os.name == "nt":
    os.system("chcp 65001 >nul 2>&1")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = ROOT
FRONTEND_DIR = os.path.join(ROOT, "DENG-main")
VENV_DIR = os.path.join(ROOT, ".venv")


def check_port(port):
    """检查端口是否被占用"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def wait_port(port, timeout=30):
    """等待端口可用"""
    for _ in range(timeout):
        if check_port(port):
            return True
        time.sleep(1)
    return False


def find_python():
    """查找 Python"""
    for cmd in [sys.executable, "py -3", "python", "python3"]:
        try:
            subprocess.run(
                cmd.split() + ["--version"],
                capture_output=True, check=True
            )
            return cmd
        except (FileNotFoundError, subprocess.CalledProcessError):
            continue
    return None


def setup_venv(python_cmd):
    """创建虚拟环境并安装依赖"""
    activate = os.path.join(VENV_DIR, "Scripts", "activate.bat")
    if not os.path.exists(activate):
        print("[1/4] 创建虚拟环境...")
        subprocess.run([python_cmd, "-m", "venv", VENV_DIR], check=True)

    pip = os.path.join(VENV_DIR, "Scripts", "pip.exe")
    req = os.path.join(ROOT, "requirements.txt")
    print("[2/4] 安装 Python 依赖...")
    subprocess.run([pip, "install", "-q", "-r", req], check=False)


def start_backend():
    """启动后端"""
    python = os.path.join(VENV_DIR, "Scripts", "python.exe")
    print("[3/5] 启动后端 (port 8000)...")

    if check_port(8000):
        print("  端口 8000 已被占用，跳过")
        return None

    proc = subprocess.Popen(
        [python, "-m", "uvicorn", "interfaces.api.server:app",
         "--host", "0.0.0.0", "--port", "8000"],
        cwd=BACKEND_DIR,
        creationflags=subprocess.CREATE_NEW_CONSOLE
    )
    return proc


def start_copilotkit():
    """启动 CopilotKit 后端 (AI 聊天)"""
    print("[4/5] 启动 CopilotKit AI 服务 (port 3001)...")

    if check_port(3001):
        print("  端口 3001 已被占用，跳过")
        return None

    server_file = os.path.join(FRONTEND_DIR, "server", "copilotkit.js")
    if not os.path.exists(server_file):
        print("  copilotkit.js 不存在，跳过")
        return None

    npm = "npm.cmd" if os.name == "nt" else "npm"
    proc = subprocess.Popen(
        ["node", server_file],
        cwd=FRONTEND_DIR,
        creationflags=subprocess.CREATE_NEW_CONSOLE
    )
    return proc


def start_frontend():
    """启动前端"""
    print("[5/5] 启动前端 (port 3000)...")

    if check_port(3000):
        print("  端口 3000 已被占用，跳过")
        return None

    npm = "npm.cmd" if os.name == "nt" else "npm"
    proc = subprocess.Popen(
        [npm, "run", "dev"],
        cwd=FRONTEND_DIR,
        creationflags=subprocess.CREATE_NEW_CONSOLE
    )
    return proc


def main():
    print("=" * 50)
    print("  DVexa v1.0 - AI Stock Research Terminal")
    print("=" * 50)
    print()

    # 检查 Node.js
    try:
        subprocess.run(["node", "--version"], capture_output=True, check=True)
    except FileNotFoundError:
        print("ERROR: Node.js 未安装，请从 nodejs.org 安装")
        input("按回车退出...")
        return

    # 检查 Python
    python_cmd = find_python()
    if not python_cmd:
        print("ERROR: Python 未安装，请从 python.org 安装")
        input("按回车退出...")
        return

    # 安装依赖
    setup_venv(python_cmd)

    # 启动后端
    start_backend()

    # 启动 CopilotKit AI 服务
    start_copilotkit()

    # 启动前端
    start_frontend()

    # 等待并打开浏览器
    print()
    print("等待服务启动...")
    if wait_port(3000, timeout=15):
        print("前端就绪，打开浏览器...")
        webbrowser.open("http://localhost:3000")
    else:
        print("前端启动超时，请手动打开 http://localhost:3000")

    print()
    print("=" * 50)
    print("  后端: http://localhost:8000/docs")
    print("  前端: http://localhost:3000")
    print("  AI助手: http://localhost:3001")
    print("  关闭此窗口不影响服务运行")
    print("=" * 50)
    input("按回车退出启动器...")


if __name__ == "__main__":
    main()
