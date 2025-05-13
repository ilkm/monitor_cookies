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

# 获取配置文件路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITES_CONFIG_FILE = os.path.join(BASE_DIR, "sites.json")
os.makedirs(BASE_DIR, exist_ok=True)

# 页面刷新定时任务
async def periodic_refresh_pages(app):
    """每5分钟刷新一次所有正在监控的页面"""
    config = get_config_item("config")
    refresh_interval = config.get("refresh_interval", 3000)
    # 用户活动检测时间阈值（秒），默认60秒内有活动则认为用户正在操作
    user_activity_threshold = config.get("user_activity_threshold", 60)
    
    while True:
        try:
            await asyncio.sleep(refresh_interval)  # 默认5分钟刷新一次
            tasks = getattr(app.state, "monitor_tasks", {})
            pages = getattr(app.state, "monitor_pages", {})
            
            if not pages:
                print("[定时刷新] 没有正在监控的页面")
                continue
                
            print(f"[定时刷新] 开始检查 {len(pages)} 个页面")
            
            for task_key, page in list(pages.items()):
                try:
                    task = tasks.get(task_key)
                    if task and not task.done() and not task.cancelled():
                        # 检查页面是否有用户活动
                        try:
                            # 注入检测代码（如果尚未注入）
                            await page.evaluate("""
                                if (!window._lastUserActivity) {
                                    window._lastUserActivity = Date.now();
                                    document.addEventListener('mousemove', () => { window._lastUserActivity = Date.now(); });
                                    document.addEventListener('keydown', () => { window._lastUserActivity = Date.now(); });
                                    document.addEventListener('click', () => { window._lastUserActivity = Date.now(); });
                                    document.addEventListener('scroll', () => { window._lastUserActivity = Date.now(); });
                                }
                            """)
                            
                            # 获取最后活动时间
                            last_activity = await page.evaluate("window._lastUserActivity || 0")
                            current_time = await page.evaluate("Date.now()")
                            idle_time = (current_time - last_activity) / 1000  # 转为秒
                            
                            if idle_time < user_activity_threshold:
                                print(f"[定时刷新] 检测到用户活动，跳过刷新: {task_key}, 闲置时间: {idle_time:.1f}秒")
                                continue
                            
                            # 用户长时间未操作，可以安全刷新
                            print(f"[定时刷新] 用户无活动，执行刷新: {task_key}, 闲置时间: {idle_time:.1f}秒")
                            await page.reload()
                        except Exception as activity_error:
                            # 检测失败，保守处理，不刷新页面
                            print(f"[警告] 检测用户活动失败: {task_key}, 错误: {activity_error}")
                            # 如果检测失败则默认刷新
                            await page.reload()
                    else:
                        pages.pop(task_key, None)
                except Exception as e:
                    print(f"[异常] 刷新页面失败: {task_key}, 错误: {e}\n{traceback.format_exc()}")
        except asyncio.CancelledError:
            print("[定时刷新] 定时任务被取消")
            break
        except Exception as e:
            print(f"[异常] 定时刷新任务异常: {e}\n{traceback.format_exc()}")
            await asyncio.sleep(60)

class SiteConfig(BaseModel):
    code: int
    account_type: int
    account: str
    password: str
    contact: str
    description: Optional[str] = None

class UserConfig(BaseModel):
    user_id: int
    sites: List[SiteConfig]

class MediaTypeConfig(BaseModel):
    name: str
    url: str
    domains: List[str]

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
            return json.load(f)
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

def get_config_item(item_type, item_id=None, sub_item_id=None):
    """统一获取配置项的函数"""
    data = load_all_data()
    
    if item_type == "user":
        return next((user for user in data.get("users", []) if user["user_id"] == item_id), None)
    elif item_type == "site":
        user = next((user for user in data.get("users", []) if user["user_id"] == item_id), None)
        return next((site for site in user.get("sites", []) if site["code"] == sub_item_id), None) if user else None
    elif item_type == "media":
        return data.get("config", {}).get("media_codes", {}).get(str(item_id), None)
    elif item_type == "account_types":
        return data.get("config", {}).get("account_types", {})
    elif item_type == "config":
        return data.get("config", {})
    elif item_type == "media_codes":
        return data.get("config", {}).get("media_codes", {})
    elif item_type == "users":
        return data.get("users", [])
    return None

@asynccontextmanager
async def lifespan(app):
    # 启动初始化
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
    
    # 关闭浏览器
    print("Stopping browser manager...")
    try:
        await browser_manager.stop_browser()
    except Exception as e:
        print(f"Error during browser shutdown: {e}")
    print("Browser manager stopped.")
    print("Server shutdown.")

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="server/static", html=True), name="static")

# ------------------ 监控配置信息接口 ------------------

@app.get("/api/sites")
def get_sites():
    """聚合返回所有站点。"""
    return load_all_data()

@app.get("/api/config")
def get_config():
    """返回全局配置config部分。"""
    return get_config_item("config")

@app.get("/api/config/media_codes")
def get_media_codes():
    """返回config.media_codes部分。"""
    return get_config_item("media_codes")

@app.get("/api/users")
def get_users():
    """返回所有用户及其站点。"""
    return get_config_item("users")

# ------------------ browser 操作相关接口 ------------------

async def _cleanup_browser_state(request: Request):
    """清理所有监控任务和页面引用"""
    tasks = getattr(request.app.state, "monitor_tasks", {})
    for task_key in list(tasks.keys()):
        task = tasks[task_key]
        task.cancel()
        del tasks[task_key]
    pages = getattr(request.app.state, "monitor_pages", {})
    for page_key in list(pages.keys()):
        del pages[page_key]

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
    await _cleanup_browser_state(request)
    await request.app.state.browser_manager.stop_browser()
    return {"msg": "浏览器已关闭"}

@app.post("/api/browser/restart")
async def api_restart_browser(request: Request):
    """重启浏览器。"""
    await _cleanup_browser_state(request)
    await request.app.state.browser_manager.restart_browser()
    return {"msg": "浏览器已重启"}

# ------------------ 监控任务相关接口 ------------------

async def validate_monitor_params(params):
    """验证监控参数"""
    user_id = params.get("user_id")
    site_code = params.get("site_code")
    
    if not user_id: 
        raise HTTPException(status_code=400, detail="user_id为必填参数")
    if not site_code:
        raise HTTPException(status_code=400, detail="site_code为必填参数")
        
    user = get_config_item("user", user_id)
    if not user:
        raise HTTPException(status_code=400, detail=f"user_id:{user_id} 不存在，请先添加用户")
        
    site = get_config_item("site", user_id, site_code)
    if not site:
        raise HTTPException(status_code=400, detail=f"user_id:{user_id} site_code:{site_code} 不存在，请先添加站点")
        
    media = get_config_item("media", site_code)
    if not media:
        raise HTTPException(status_code=400, detail=f"user_id:{user_id} site_code:{site_code} 媒体类型不存在，请先去监控配置中维护媒体类型")
        
    return user_id, site_code, media

@app.post("/api/monitor/start")
async def api_monitor_start(request: Request):
    """启动指定用户、站点、url的Fetch/XHR监控任务。"""
    params = await request.json()
    user_id, site_code, media = await validate_monitor_params(params)
    
    # 唯一key
    task_key = f"{user_id}:{site_code}:{media['url']}"
    
    # 检查是否已存在
    if hasattr(request.app.state, "monitor_tasks") and task_key in request.app.state.monitor_tasks:
        # 调用get_page
        await request.app.state.browser_manager.get_page(str(user_id), str(site_code), media['url'])
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
    user_id, site_code, media = await validate_monitor_params(params)
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
    user_id, site_code, media = await validate_monitor_params(params)
    
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
    user_id, site_code, media = await validate_monitor_params(params)

    task_key = f"{user_id}:{site_code}:{media['url']}"
    tasks = getattr(request.app.state, "monitor_tasks", {})
    task = tasks.get(task_key)
    if not task:
        return {"code": 404, "exists": False, "running": False, "msg": "未找到该监控任务"}
    running = not task.done() and not task.cancelled()
    return {"code": 200, "exists": True, "running": running, "msg": f"监控任务{'正在运行' if running else '已停止'}: {task_key}"}

@app.get("/")
def root():
    """访问根路径时自动重定向到前端静态页面"""
    return RedirectResponse(url="/static")