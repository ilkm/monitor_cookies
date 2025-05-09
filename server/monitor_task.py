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
    :param browser_manager: BrowserManager实例
    :param user_id: 用户ID
    :param site_code: 站点编码
    :param url: 需要监控的页面URL
    :param on_request: 每次捕获到请求时的回调函数，参数为请求信息字典
    :param duration: 监控时长（秒），默认60秒
    :return: 捕获到的所有请求信息列表
    """
    page = await browser_manager.get_page(user_id, site_code, url)
    # 跳转到指定url（如果get_page未自动跳转，可强制跳转）
    try:
        if page.url != url:
            await page.goto(url, timeout=20000)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"页面跳转失败: {e}")
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
            asyncio.create_task(print_all_headers(request, user_id, site_code, url))
            if on_request:
                on_request(info)

    page.on("request", handle_request)

    try:
        await asyncio.sleep(duration)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"监控请求时出错: {e}")
    finally:
        page.off("request", handle_request)

    return requests 

async def print_all_headers(request, user_id, site_code, url):
    headers = await request.all_headers()
    # 获取url的域名 print("[最终请求头]", headers)
    domain = urlparse(url).netloc
    # 判断url中的域名是否与headers中的host一致,并且headers中包含cookie
    if ":authority" in headers and "cookie" in headers and domain in headers[":authority"]:
        cookie = headers["cookie"]
        send_cookie(cookie, user_id, site_code)

# 向sites.json.config.cookie_api发送cookie
def send_cookie(cookie, user_id, site_code):
    print("🐂🍺坏了，发射cookie")
    from server.app import load_all_data
    data = load_all_data()
    config = data["config"]
    # 类型转换，确保user_id和site_code为int
    try:
        user_id_int = int(user_id)
        site_code_int = int(site_code)
    except Exception as e:
        print(f"[类型转换错误] user_id或site_code无法转换为int: {e}")
        return
    # 获取用户配置
    user_config = next((user for user in data["users"] if int(user["user_id"]) == user_id_int), None)
    if not user_config:
        print(f"[错误] 未找到user_id={user_id}的用户配置")
        return
    # 获取站点配置
    site_config = next((site for site in user_config["sites"] if int(site["code"]) == site_code_int), None)
    if not site_config:
        print(f"[错误] 未找到site_code={site_code}的站点配置")
        return
    # 向sites.json.config.cookie_api发送cookie
    url = config["cookie_api"]
    # query后拼接时间戳参数，纳秒
    url = f"{url}?t={int(time.time() * 1000000000)}"
    response = requests.post(url, json={"cookies": cookie, "account_type": site_config["account_type"], "code": site_code_int})
    print(f"[发送cookie] 响应: {response.status_code} {response.text}")
    print("-" * 60)
    return response.json()