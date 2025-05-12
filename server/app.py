from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os
import json
from typing import Dict, Optional, List
from contextlib import asynccontextmanager
from browser_manager.manager import BrowserManager
import server.monitor_task
import asyncio
import traceback
from fastapi.responses import RedirectResponse

# 获取当前文件（app.py）所在目录的上一级目录（即项目根目录）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = BASE_DIR  # 现在config目录就是根目录
SITES_CONFIG_FILE = os.path.join(CONFIG_DIR, "sites.json")
os.makedirs(CONFIG_DIR, exist_ok=True)

# 页面刷新定时任务
async def periodic_refresh_pages(app):
    """每5分钟刷新一次所有正在监控的页面"""
    while True:
        try:
            await asyncio.sleep(300)  # 5分钟 = 300秒
            
            # 获取所有监控任务
            tasks = getattr(app.state, "monitor_tasks", {})
            pages = getattr(app.state, "monitor_pages", {})
            
            if not pages:
                print("[定时刷新] 没有正在监控的页面")
                continue
                
            print(f"[定时刷新] 开始刷新 {len(pages)} 个页面")
            
            # 遍历所有页面并刷新
            for task_key, page in list(pages.items()):
                try:
                    # 检查对应的任务是否仍在运行
                    task = tasks.get(task_key)
                    if task and not task.done() and not task.cancelled():
                        print(f"[定时刷新] 刷新页面: {task_key}")
                        await page.reload()
                        print(f"[定时刷新] 页面刷新成功: {task_key}")
                    else:
                        # 任务已结束，从页面字典中移除
                        print(f"[定时刷新] 任务已结束，移除页面: {task_key}")
                        pages.pop(task_key, None)
                except Exception as e:
                    print(f"[异常] 刷新页面失败: {task_key}, 错误: {e}\n{traceback.format_exc()}")
        except asyncio.CancelledError:
            print("[定时刷新] 定时任务被取消")
            break
        except Exception as e:
            print(f"[异常] 定时刷新任务异常: {e}\n{traceback.format_exc()}")
            # 出错后等待一段时间再继续
            await asyncio.sleep(60)

class SiteConfig(BaseModel):
    code: int  # 站点编码
    account_type: int  # 账号类型
    account: str  # 账号/手机号
    password: str  # 密码
    contact: str  # 负责人
    description: Optional[str] = None  # 描述，可选

class UserConfig(BaseModel):
    user_id: int  # 用户ID
    sites: List[SiteConfig]  # 该用户下的所有站点

class MediaTypeConfig(BaseModel):
    name: str  # 媒体类型名称
    url: str  # 平台URL
    domains: List[str]  # 域名列表

class GlobalConfig(BaseModel):
    cookie_api: str
    headless_mode: bool
    performance_mode: bool
    media_codes: Dict[str, MediaTypeConfig]

class AllConfig(BaseModel):
    users: List[UserConfig]
    config: GlobalConfig

def load_all_data() -> dict:
    """读取整个 sites.json 文件，返回字典对象。"""
    if not os.path.exists(SITES_CONFIG_FILE):
        return {}
    try:
        with open(SITES_CONFIG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except Exception as e:
        print(f"Error loading {SITES_CONFIG_FILE}: {e}")
        return {}

def save_all_data(data: dict):
    """保存整个 sites.json 文件内容。"""
    try:
        with open(SITES_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving {SITES_CONFIG_FILE}: {e}")

def get_user_config(user_id: int) -> UserConfig:
    """根据用户ID获取用户配置。"""
    data = load_all_data()
    return next((user for user in data.get("users", []) if user["user_id"] == user_id), None)

def get_site_config(user_id: int, site_code: int) -> SiteConfig:
    """根据用户ID和站点编码获取站点配置。"""
    user = get_user_config(user_id)
    return next((site for site in user.get("sites", []) if site["code"] == site_code), None)

def get_media_config(media_code) -> MediaTypeConfig:
    """根据媒体编码获取媒体配置。"""
    data = load_all_data()
    media_code_str = str(media_code)  # 强制转为字符串
    return data.get("config", {}).get("media_codes", {}).get(media_code_str, None)

@asynccontextmanager
async def lifespan(app):
    # 启动时初始化 browser_manager
    browser_manager = BrowserManager()
    await browser_manager.start_browser(headless=False)
    app.state.browser_manager = browser_manager
    
    # 初始化监控任务和页面字典
    app.state.monitor_tasks = {}
    app.state.monitor_pages = {}
    
    # 启动定时刷新页面任务
    app.state.refresh_task = asyncio.create_task(periodic_refresh_pages(app))
    
    print("Browser manager started.")
    print("Page refresh task started (every 5 minutes).")
    print(f"Site configurations will be loaded from: {os.path.abspath(SITES_CONFIG_FILE)}")
    
    yield
    
    # 关闭时取消定时刷新任务
    if hasattr(app.state, "refresh_task"):
        app.state.refresh_task.cancel()
        print("Page refresh task stopped.")
    
    # 关闭时自动关闭 browser_manager
    print("Stopping browser manager...")
    try:
        await browser_manager.stop_browser()
    except Exception as e:
        print(f"Error during browser shutdown: {e}")
    print("Browser manager stopped.")
    print("Server shutdown.")

app = FastAPI(lifespan=lifespan)
# 挂载静态资源到/static路径，避免覆盖API接口
app.mount("/static", StaticFiles(directory="server/static", html=True), name="static")

# ------------------ 监控配置信息接口 ------------------

@app.get("/api/sites")
def get_sites():
    """聚合返回所有站点。"""
    return load_all_data()

@app.get("/api/config")
def get_config():
    """返回全局配置config部分。"""
    data = load_all_data()
    return data.get("config", {})

@app.get("/api/config/media_codes")
def get_media_codes():
    """返回config.media_codes部分。"""
    data = load_all_data()
    return data.get("config", {}).get("media_codes", {})

@app.get("/api/users")
def get_users():
    """返回所有用户及其站点。"""
    data = load_all_data()
    return data.get("users", [])

# ------------------ browser 操作相关接口 ------------------

@app.post("/api/browser/start")
async def api_start_browser(request: Request):
    """启动浏览器，可选headless参数。"""
    params = await request.json()
    headless = params.get("headless", False)
    await request.app.state.browser_manager.start_browser(headless=headless)
    return {"msg": "浏览器已启动", "headless": headless}

@app.post("/api/browser/stop")
async def api_stop_browser(request: Request):
    """关闭浏览器。"""
    await request.app.state.browser_manager.stop_browser()
    return {"msg": "浏览器已关闭"}

@app.post("/api/browser/restart")
async def api_restart_browser(request: Request):
    """重启浏览器。"""
    await request.app.state.browser_manager.restart_browser()
    return {"msg": "浏览器已重启"}

# ------------------ 监控任务相关接口 ------------------

@app.post("/api/monitor/start")
async def api_monitor_start(request: Request):
    """启动指定用户、站点、url的Fetch/XHR监控任务。"""
    params = await request.json()
    user_id = params.get("user_id")
    site_code = params.get("site_code")
    if not user_id: 
        raise HTTPException(status_code=400, detail="user_id为必填参数")
    if not site_code:
        raise HTTPException(status_code=400, detail="site_code为必填参数")
    user = get_user_config(user_id)
    if not user:
        raise HTTPException(status_code=400, detail=f"user_id:{user_id} 不存在，请先添加用户")
    site = get_site_config(user_id, site_code)
    if not site:
        raise HTTPException(status_code=400, detail=f"user_id:{user_id} site_code:{site_code} 不存在，请先添加站点")
    media = get_media_config(site['code'])
    if not media:
        raise HTTPException(status_code=400, detail=f"user_id:{user_id} site_code:{site_code} 媒体类型不存在，请先去监控配置中维护媒体类型")
    # 唯一key
    task_key = f"{user_id}:{site_code}:{media['url']}"
    # 检查是否已存在
    if hasattr(request.app.state, "monitor_tasks") and task_key in request.app.state.monitor_tasks:
        # 调用get_page
        page = await request.app.state.browser_manager.get_page(str(user_id), str(site_code), media['url'])
        raise HTTPException(status_code=400, detail="该监控任务已存在")
    
    # 先获取页面，用于定时刷新
    try:
        page = await request.app.state.browser_manager.get_page(str(user_id), str(site_code), media['url'])
        # 存储页面对象，用于定时刷新
        request.app.state.monitor_pages[task_key] = page
    except Exception as e:
        print(f"[异常] 获取页面失败: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"获取页面失败: {e}")
    
    # 启动任务
    task = asyncio.create_task(
        server.monitor_task.monitor_fetch_requests(
            request.app.state.browser_manager, str(user_id), str(site_code), media['url'], duration=0x7fffffff
        )
    )
    if not hasattr(request.app.state, "monitor_tasks"):
        request.app.state.monitor_tasks = {}
    request.app.state.monitor_tasks[task_key] = task
    return {"msg": f"已启动监控任务: {task_key}"}

@app.post("/api/monitor/stop")
async def api_monitor_stop(request: Request):
    """暂停指定监控任务。"""
    params = await request.json()
    user_id = params.get("user_id")
    site_code = params.get("site_code")
    if not user_id or not site_code:
        raise HTTPException(status_code=400, detail="user_id、site_code均为必填参数")
    media = get_media_config(site_code)
    if not media:
        raise HTTPException(status_code=400, detail=f"user_id:{user_id} site_code:{site_code} 媒体类型不存在，请先去监控配置中维护媒体类型")
    task_key = f"{user_id}:{site_code}:{media['url']}"
    
    # 从任务字典中移除
    tasks = getattr(request.app.state, "monitor_tasks", {})
    task = tasks.get(task_key)
    if not task:
        raise HTTPException(status_code=404, detail=f"未找到监控任务: {task_key}")
    task.cancel()
    del tasks[task_key]
    
    # 从页面字典中移除
    pages = getattr(request.app.state, "monitor_pages", {})
    if task_key in pages:
        del pages[task_key]
    
    await request.app.state.browser_manager.close_page(str(user_id), str(site_code))
    return {"msg": f"已暂停监控任务: {task_key}"}

@app.post("/api/monitor/restart")
async def api_monitor_restart(request: Request):
    """重启指定监控任务。"""
    params = await request.json()
    user_id = params.get("user_id")
    site_code = params.get("site_code")
    if not user_id or not site_code:
        raise HTTPException(status_code=400, detail="user_id、site_code均为必填参数")
    media = get_media_config(site_code)
    if not media:
        raise HTTPException(status_code=400, detail=f"user_id:{user_id} site_code:{site_code} 媒体类型不存在，请先去监控配置中维护媒体类型")
    # 先停再启
    task_key = f"{user_id}:{site_code}:{media['url']}"
    tasks = getattr(request.app.state, "monitor_tasks", {})
    old_task = tasks.get(task_key)
    if old_task:
        old_task.cancel()
        del tasks[task_key]
    
    # 先获取页面，用于定时刷新
    try:
        page = await request.app.state.browser_manager.get_page(str(user_id), str(site_code), media['url'])
        # 存储页面对象，用于定时刷新
        request.app.state.monitor_pages[task_key] = page
    except Exception as e:
        print(f"[异常] 获取页面失败: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"获取页面失败: {e}")
    
    # 启动新任务
    task = asyncio.create_task(
        server.monitor_task.monitor_fetch_requests(
            request.app.state.browser_manager, str(user_id), str(site_code), media['url'], duration=0x7fffffff
        )
    )
    tasks[task_key] = task
    return {"msg": f"已重启监控任务: {task_key}"}

@app.post("/api/monitor/status")
async def api_monitor_status(request: Request):
    """查询指定监控任务的状态。"""
    params = await request.json()
    user_id = params.get("user_id")
    site_code = params.get("site_code")
    
    if not user_id or not site_code:
        raise HTTPException(status_code=400, detail="user_id、site_code均为必填参数")
    media = get_media_config(site_code)
    if not media:
        raise HTTPException(status_code=400, detail=f"user_id:{user_id} site_code:{site_code} 媒体类型不存在，请先去监控配置中维护媒体类型")

    task_key = f"{user_id}:{site_code}:{media['url']}"
    tasks = getattr(request.app.state, "monitor_tasks", {})
    task = tasks.get(task_key)
    if not task:
        return {"code": 404, "exists": False, "running": False, "msg": "未找到该监控任务"}
    running = not task.done() and not task.cancelled()
    return {"code": 200, "exists": True, "running": running, "msg": f"监控任务{'正在运行' if running else '已停止'}: {task_key}"}

@app.get("/")
def root():
    """
    访问根路径时自动重定向到前端静态页面
    """
    return RedirectResponse(url="/static")