import uvicorn
from server.app import app, get_local_ip  # FastAPI app 及获取本机IP方法

if __name__ == "__main__":
    local_ip = get_local_ip()
    print(f"服务已启动，可通过 http://{local_ip}:8000 在局域网访问")
    uvicorn.run(app, host="0.0.0.0", port=8000)
