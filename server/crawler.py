# -*- coding: utf-8 -*-
"""
爬虫相关API，供app.py调用
"""

from fastapi import HTTPException
from typing import Any

async def get_cookies(browser_manager, user_id: str, site_code: str) -> Any:
    """根据user_id和site_code获取站点cookies。"""
    # 获取/创建页面
    page = await browser_manager.get_page(user_id, site_code, None)
    # 获取cookies
    try:
        cookies = await page.context.cookies()
        return cookies
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取Cookies失败: {e}")

async def refresh_page(browser_manager, user_id: str, site_code: str) -> str:
    """根据user_id和site_code刷新页面。"""
    page = await browser_manager.get_page(user_id, site_code, None)
    try:
        await page.reload()
        return "页面已刷新"
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"刷新页面失败: {e}")

async def get_annotated_html(browser_manager, user_id: str, site_code: str) -> str:
    """根据user_id和site_code获取带注释的html模板。"""
    page = await browser_manager.get_page(user_id, site_code, None)
    try:
        html = await page.content()
        # 这里可以根据实际需求对html进行注释处理
        annotated_html = f"<!-- 这是{user_id}的{site_code}页面 -->\n" + html
        return annotated_html
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取HTML失败: {e}")
