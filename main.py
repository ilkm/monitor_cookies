import uvicorn
from server.app import app
import socket

def get_local_ip():
    """获取本机局域网IP地址"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # 连接到一个外部IP（不需要实际连通）
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

if __name__ == "__main__":
    uvicorn.run(app, host=get_local_ip(), port=8000)
