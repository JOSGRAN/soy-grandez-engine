from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright
from typing import Optional, Dict, Any, List
from config.settings import settings
import logging
import random
import asyncio

logger = logging.getLogger(__name__)


class BrowserManager:
    def __init__(
        self,
        headless: bool = True,
        user_agent: Optional[str] = None,
        proxy: Optional[Dict[str, str]] = None
    ):
        self.headless = headless
        self.user_agent = user_agent or self._get_random_user_agent()
        self.proxy = proxy
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
    
    def _get_random_user_agent(self) -> str:
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15"
        ]
        return random.choice(user_agents)
    
    async def start(self):
        try:
            self.playwright = await async_playwright().start()
            
            browser_args = [
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process"
            ]
            
            launch_options = {
                "headless": self.headless,
                "args": browser_args,
                "ignore_default_args": ["--enable-automation"]
            }
            
            if self.proxy:
                launch_options["proxy"] = {
                    "server": f"{self.proxy.get('protocol', 'http')}://{self.proxy.get('host')}:{self.proxy.get('port')}",
                    "username": self.proxy.get("username"),
                    "password": self.proxy.get("password")
                }
            
            self.browser = await self.playwright.chromium.launch(**launch_options)
            
            context_options = {
                "user_agent": self.user_agent,
                "viewport": {"width": 1920, "height": 1080},
                "locale": "en-US",
                "timezone_id": "America/New_York",
                "permissions": ["geolocation"],
                "geolocation": {"latitude": 40.7128, "longitude": -74.0060},
                "ignore_https_errors": True,
                "java_script_enabled": True
            }
            
            self.context = await self.browser.new_context(**context_options)
            
            # Inject anti-detection scripts
            await self.context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });
                
                window.chrome = {
                    runtime: {}
                };
            """)
            
            # Asignar automáticamente la página principal por defecto
            self.page = await self.context.new_page()
            return True
            
        except Exception as e:
            logger.error(f"Error starting browser: {e}")
            return False

    async def new_page(self) -> Page:
        """Crea y retorna una nueva página adicional del navegador."""
        if not self.browser or not self.context:
            await self.start()
        return await self.context.new_page()
    
    async def navigate(self, url: str, wait_until: str = "networkidle") -> bool:
        try:
            await self.page.goto(url, wait_until=wait_until, timeout=30000)
            logger.info(f"Navigated to: {url}")
            return True
        except Exception as e:
            logger.error(f"Error navigating to {url}: {e}")
            return False
    
    async def wait_for_selector(self, selector: str, timeout: int = 10000) -> bool:
        try:
            await self.page.wait_for_selector(selector, timeout=timeout)
            return True
        except Exception as e:
            logger.error(f"Error waiting for selector {selector}: {e}")
            return False
    
    async def click(self, selector: str, timeout: int = 10000) -> bool:
        try:
            await self.page.click(selector, timeout=timeout)
            return True
        except Exception as e:
            logger.error(f"Error clicking {selector}: {e}")
            return False
    
    async def fill(self, selector: str, value: str, timeout: int = 10000) -> bool:
        try:
            await self.page.fill(selector, value, timeout=timeout)
            return True
        except Exception as e:
            logger.error(f"Error filling {selector}: {e}")
            return False
    
    async def type_text(self, selector: str, text: str, delay: int = 50) -> bool:
        try:
            await self.page.type(selector, text, delay=delay)
            return True
        except Exception as e:
            logger.error(f"Error typing in {selector}: {e}")
            return False
    
    async def get_text(self, selector: str) -> Optional[str]:
        try:
            element = await self.page.query_selector(selector)
            if element:
                return await element.inner_text()
            return None
        except Exception as e:
            logger.error(f"Error getting text from {selector}: {e}")
            return None
    
    async def get_attribute(self, selector: str, attribute: str) -> Optional[str]:
        try:
            element = await self.page.query_selector(selector)
            if element:
                return await element.get_attribute(attribute)
            return None
        except Exception as e:
            logger.error(f"Error getting attribute {attribute} from {selector}: {e}")
            return None
    
    async def execute_script(self, script: str) -> Any:
        try:
            return await self.page.evaluate(script)
        except Exception as e:
            logger.error(f"Error executing script: {e}")
            return None
    
    async def wait(self, milliseconds: int):
        await asyncio.sleep(milliseconds / 1000)
    
    async def screenshot(self, path: str, full_page: bool = False) -> bool:
        try:
            await self.page.screenshot(path=path, full_page=full_page)
            logger.info(f"Screenshot saved to: {path}")
            return True
        except Exception as e:
            logger.error(f"Error taking screenshot: {e}")
            return False
    
    async def save_cookies(self, path: str) -> bool:
        try:
            cookies = await self.context.cookies()
            import json
            with open(path, 'w') as f:
                json.dump(cookies, f)
            logger.info(f"Cookies saved to: {path}")
            return True
        except Exception as e:
            logger.error(f"Error saving cookies: {e}")
            return False
    
    async def load_cookies(self, path: str) -> bool:
        try:
            import json
            with open(path, 'r') as f:
                cookies = json.load(f)
            await self.context.add_cookies(cookies)
            logger.info(f"Cookies loaded from: {path}")
            return True
        except Exception as e:
            logger.error(f"Error loading cookies: {e}")
            return False
    
    async def close(self):
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            logger.info("Browser closed successfully")
        except Exception as e:
            logger.error(f"Error closing browser: {e}")
    
    async def __aenter__(self):
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()