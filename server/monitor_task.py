# -*- coding: utf-8 -*-
"""
定时任务：监控指定用户和站点的Fetch/XHR请求
"""

import asyncio
from typing import Callable, Any
from fastapi import HTTPException
from urllib.parse import urlparse
import requests
import time

async def monitor_fetch_requests(browser_manager, user_id: str, site_code: str, url: str, on_request: Callable[[dict], Any]=None, duration: int=60):
    """
    监控指定用户和站点的Fetch/XHR请求，启动时自动跳转到url。
    """
    page = await browser_manager.get_page(user_id, site_code, url)
    requests = []

    def handle_request(request):
        # 只监控Fetch/XHR请求
        if request.resource_type in ("fetch", "xhr"):
            info = {
                "url": request.url,
                "method": request.method,
                "headers": dict(request.headers),
                "post_data": request.post_data,
                "resource_type": request.resource_type,
                "timestamp": asyncio.get_event_loop().time()
            }
            requests.append(info)
            asyncio.create_task(check_and_send_cookie(request, user_id, site_code, url))
            if on_request:
                on_request(info)

    # 添加请求监听器
    page.on("request", handle_request)

    try:
        await asyncio.sleep(duration)
    except asyncio.CancelledError:
        # 任务被取消，这是正常的，静默处理
        print(f"[信息] 监控任务已取消: user_id={user_id}, site_code={site_code}")
        # 重新抛出异常，让调用者知道任务已取消
        raise
    except Exception as e:
        # 处理其他异常
        print(f"[异常] 监控任务出错: {e}")
        raise HTTPException(status_code=500, detail=f"监控请求时出错: {e}")
    finally:
        # 移除请求监听器，使用正确的 Playwright API
        try:
            # 在 Playwright 中，移除事件监听器的正确方式是使用 removeListener
            page.remove_listener("request", handle_request)
        except Exception as e:
            # 忽略可能的错误，确保不影响主流程
            print(f"[警告] 移除请求监听器失败：{e}")

    return requests 

async def check_and_send_cookie(request, user_id, site_code, url):
    """检查并发送cookie"""
    from server.app import get_config_item
    media_config = get_config_item("media", site_code)
    if not media_config:
        return
        
    headers = await request.all_headers()
    cookie = headers.get("cookie")
    if not cookie:
        return
        
    # 提取域名信息
    domain = [extract_main_domain(urlparse(url).netloc)]
    if media_config.get("domains"):
        domain.extend(media_config.get("domains"))
    domain = list(set(domain))  # 去重
    
    host = extract_main_domain(headers.get(media_config.get("host")))
    
    if host and domain and any(domain):
        send_cookie(cookie, user_id, site_code)

def send_cookie(cookie, user_id, site_code):
    """向cookie API发送cookie"""
    print("获取Cookie，发射Cookie")
    from server.app import load_all_data
    data = load_all_data()
    config = data["config"]
    
    # 类型转换
    try:
        user_id_int = int(user_id)
        site_code_int = int(site_code)
    except Exception as e:
        print(f"[类型转换错误] user_id或site_code无法转换为int: {e}")
        return
        
    # 获取配置
    from server.app import get_config_item
    user_config = get_config_item("user", user_id_int)
    if not user_config:
        print(f"[错误] 未找到user_id={user_id}的用户配置")
        return
        
    site_config = get_config_item("site", user_id_int, site_code_int)
    if not site_config:
        print(f"[错误] 未找到site_code={site_code}的站点配置")
        return
        
    # 发送cookie
    url = f"{config['cookie_api']}?t={int(time.time() * 1000000000)}"
    json={"cookies": cookie, "account_type": site_config["account_type"], "code": site_code_int}

    response = requests.post(url, json=json)
    print(f"data: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())} url: {url}  json: {json} response: {response.status_code} {response.text}")
    print("-" * 60)
    return True

def extract_main_domain(domain_str):
    """提取主域名并加前缀点，如www.baidu.com -> .baidu.com"""
    if not domain_str:
        return ""
    parts = domain_str.split(".")
    if len(parts) >= 2:
        return "." + ".".join(parts[-2:])
    return "." + domain_str