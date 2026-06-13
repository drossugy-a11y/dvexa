"""DVexa 停止服务"""

import subprocess
import socket


def kill_port(port):
    """杀掉占用指定端口的进程"""
    try:
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True, text=True
        )
        for line in result.stdout.split("\n"):
            if f":{port}" in line and "LISTENING" in line:
                pid = line.strip().split()[-1]
                subprocess.run(["taskkill", "/PID", pid, "/F"],
                             capture_output=True)
                print(f"  已停止端口 {port} 的进程 (PID: {pid})")
    except Exception as e:
        print(f"  清理端口 {port} 失败: {e}")


def main():
    print("停止 DVexa 服务...")
    kill_port(8000)
    kill_port(3000)
    print("完成!")


if __name__ == "__main__":
    main()
