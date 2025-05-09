import asyncio
import os
import json
from playwright.async_api import async_playwright

class BrowserManager:
    def __init__(self, user_data_dir_base: str = "./user_data"):
        self.playwright = None
        self.browser = None
        self.contexts = {}  # user_id -> BrowserContext
        self.pages = {}  # (user_id, site_code) -> Page
        self.user_data_dir_base = user_data_dir_base
        os.makedirs(self.user_data_dir_base, exist_ok=True) # 确保基础目录存在

    async def start_browser(self, headless=False):
        """初始化 Playwright 并启动浏览器。"""
        if self.browser and self.browser.is_connected():
            print("Browser is already running.")
            return

        self.playwright = await async_playwright().start()
        try:
            self.browser = await self.playwright.chromium.launch(headless=headless)
            print("Browser started successfully.")
            # TODO: 实现浏览器保活/重建逻辑
            # 这可能涉及定期检查 browser.is_connected()
            # 并在断开时尝试重启。
        except Exception as e:
            print(f"Error starting browser: {e}")
            if self.playwright:
                await self.playwright.stop()
            self.playwright = None
            self.browser = None
            raise

    async def stop_browser(self):
        """关闭所有 context 和 page，然后关闭浏览器并停止 Playwright。"""
        print("Stopping browser: Closing all managed contexts...")
        # 创建 user_id 列表，避免遍历时修改字典导致问题
        all_user_ids = list(self.contexts.keys())
        for user_id in all_user_ids:
            await self.close_context(user_id, save_state=True) # 停止时保存状态

        if self.browser:
            await self.browser.close()
            self.browser = None
            print("Browser closed.")
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None
            print("Playwright stopped.")
        self.contexts.clear()
        self.pages.clear()

    async def restart_browser(self, headless=False):
        """重启浏览器。"""
        print("Restarting browser...")
        # 数据保存应由 stop_browser 处理
        await self.stop_browser()
        await self.start_browser(headless=headless)
        print("Browser restarted.")

    def _get_storage_state_path(self, user_id: str) -> str:
        """构建用户存储状态文件的路径。"""
        return os.path.join(self.user_data_dir_base, f"user_{user_id}_storage.json")

    async def save_context_storage(self, user_id: str):
        """将用户 context 的存储状态保存到文件。"""
        if user_id not in self.contexts:
            print(f"No active context for user_id: {user_id} to save.")
            return

        context = self.contexts[user_id]
        if context: # 确保 context 不为 None
            storage_state_path = self._get_storage_state_path(user_id)
            try:
                storage_state = await context.storage_state()
                with open(storage_state_path, 'w') as f:
                    json.dump(storage_state, f)
                print(f"Saved storage state for user_id: {user_id} to {storage_state_path}")
            except Exception as e:
                print(f"Error saving storage state for user_id {user_id}: {e}")

    async def get_context(self, user_id: str):
        """
        获取已存在或新建的指定 user_id 的浏览器 context。
        如果存在 user_data_dir_base/user_{user_id}_storage.json，则加载存储状态。
        """
        if not self.browser or not self.browser.is_connected():
            # 如果未连接，尝试重启浏览器
            print("Browser not connected. Attempting to restart...")
            await self.start_browser(headless=self.browser.launch_options.get('headless', False) if self.browser and hasattr(self.browser, 'launch_options') else False)
            if not self.browser or not self.browser.is_connected():
                 raise Exception("Browser not started or disconnected. Call start_browser() first or check connection.")

        if user_id in self.contexts:
            # 检查 context 是否仍可用（如未关闭）
            # Playwright 的 context 没有简单的 is_connected 或 is_closed 属性可直接判断
            # 这里假设只要在字典中就是活跃的。
            # 如果后续操作失败，再在对应处处理。
            print(f"Reusing existing context for user_id: {user_id}")
            return self.contexts[user_id]

        storage_state_path = self._get_storage_state_path(user_id)
        storage_state = None
        if os.path.exists(storage_state_path):
            try:
                with open(storage_state_path, 'r') as f:
                    storage_state = json.load(f)
                print(f"Loaded storage state for user_id: {user_id} from {storage_state_path}")
            except Exception as e:
                print(f"Error loading storage state for user_id {user_id} from {storage_state_path}: {e}. Creating new context without it.")
                # 可选：备份损坏的文件 os.rename(storage_state_path, storage_state_path + ".bak")

        print(f"Creating new context for user_id: {user_id}")
        try:
            context = await self.browser.new_context(storage_state=storage_state)
            # 为 context 关闭添加监听器以便从追踪中移除
            # context.on("close", lambda: self.contexts.pop(user_id, None)) # 需要 async lambda 或包装器
            self.contexts[user_id] = context
            return context
        except Exception as e:
            print(f"Error creating new context for user_id {user_id}: {e}")
            # 如果因存储状态创建 context 失败，清理存储状态文件，避免死循环
            # if storage_state and os.path.exists(storage_state_path):
            #     print(f"Removing potentially corrupt storage state file: {storage_state_path}")
            #     os.remove(storage_state_path)
            raise

    async def get_page(self, user_id: str, site_code: str, url: str):
        """
        获取已存在或新建的用户 context 下的页面。
        页面由 (user_id, site_code) 唯一标识。
        """
        page_key = (user_id, site_code)

        if page_key in self.pages:
            page = self.pages[page_key]
            # 检查页面是否已关闭
            if not page.is_closed():
                print(f"Reusing existing page for user: {user_id}, site_code: {site_code}")
                return page
            else:
                print(f"Page for user_id: {user_id}, site_code: {site_code} was closed. Creating a new one.")
                del self.pages[page_key] # 移除已关闭页面

        context = await self.get_context(user_id)
        if not context:
            raise Exception(f"Failed to get or create context for user_id: {user_id}")

        page = await context.new_page()
        self.pages[page_key] = page
        print(f"Created new page for user_id: {user_id}, site_code: {site_code}")

        await page.goto(url, timeout=20000)
        await page.wait_for_load_state('networkidle', timeout=10000)
        return page

    async def close_context(self, user_id: str, save_state: bool = True):
        """关闭指定用户的 context 及其所有页面，可选是否保存状态。"""
        if user_id in self.contexts:
            if save_state:
                await self.save_context_storage(user_id)

            context = self.contexts.pop(user_id)
            await context.close() # 这也会关闭该 context 下所有页面。
            
            # 从追踪中移除相关页面
            pages_to_remove = [pk for pk in self.pages if pk[0] == user_id]
            for pk in pages_to_remove:
                # context.close() 已关闭页面，这里只需从字典移除
                del self.pages[pk]
            print(f"Closed context and associated pages for user_id: {user_id}")
        else:
            print(f"No active context found for user_id: {user_id} to close.")

    async def close_page(self, user_id: str, site_code: str):
        """关闭指定页面。"""
        page_key = (user_id, site_code)
        if page_key in self.pages:
            page = self.pages.pop(page_key)
            if not page.is_closed():
                await page.close()
            print(f"Closed page for user_id: {user_id}, site_code: {site_code}")
        else:
            print(f"No active page found for (user_id: {user_id}, site_code: {site_code}) to close.")