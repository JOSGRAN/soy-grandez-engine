import httpx
import asyncio
from typing import Optional, Dict, Any
from config.settings import settings
import logging
import json

logger = logging.getLogger(__name__)


class CapsolverService:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.base_url = "https://api.capsolver.com"
        self.client = httpx.AsyncClient(timeout=60.0)
    
    async def create_task(self, task_data: Dict[str, Any]) -> Optional[str]:
        try:
            payload = {
                "clientKey": self.api_key,
                "task": task_data
            }
            
            response = await self.client.post(
                f"{self.base_url}/createTask",
                json=payload
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("errorId") == 0:
                    task_id = result.get("taskId")
                    logger.info(f"Capsolver task created: {task_id}")
                    return task_id
                else:
                    logger.error(f"Capsolver error: {result.get('errorDescription')}")
                    return None
            else:
                logger.error(f"Capsolver API error: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error creating Capsolver task: {e}")
            return None
    
    async def get_task_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        max_retries = 30
        retry_interval = 2
        
        for attempt in range(max_retries):
            try:
                payload = {
                    "clientKey": self.api_key,
                    "taskId": task_id
                }
                
                response = await self.client.post(
                    f"{self.base_url}/getTaskResult",
                    json=payload
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get("errorId") == 0:
                        status = result.get("status")
                        if status == "ready":
                            logger.info(f"Capsolver task {task_id} completed")
                            return result.get("solution")
                        elif status == "processing":
                            logger.debug(f"Task {task_id} still processing... (attempt {attempt + 1})")
                            await asyncio.sleep(retry_interval)
                        else:
                            logger.error(f"Task {task_id} failed with status: {status}")
                            return None
                    else:
                        logger.error(f"Capsolver error: {result.get('errorDescription')}")
                        return None
                else:
                    logger.error(f"Capsolver API error: {response.status_code}")
                    return None
                    
            except Exception as e:
                logger.error(f"Error getting Capsolver task result: {e}")
                await asyncio.sleep(retry_interval)
        
        logger.error(f"Task {task_id} timed out after {max_retries} attempts")
        return None
    
    async def solve_turnstile(self, website_url: str, website_key: str, page_data: Optional[str] = None) -> Optional[str]:
        task_data = {
            "type": "AntiTurnstileTaskProxyLess",
            "websiteURL": website_url,
            "websiteKey": website_key,
        }
        
        if page_data:
            task_data["pageData"] = page_data
        
        task_id = await self.create_task(task_data)
        if not task_id:
            return None
        
        solution = await self.get_task_result(task_id)
        if solution:
            return solution.get("token")
        return None
    
    async def solve_recaptcha_v2(self, website_url: str, website_key: str, is_invisible: bool = False) -> Optional[str]:
        task_type = "ReCaptchaV2TaskProxyLess" if not is_invisible else "ReCaptchaV2EnterpriseTaskProxyLess"
        
        task_data = {
            "type": task_type,
            "websiteURL": website_url,
            "websiteKey": website_key,
        }
        
        task_id = await self.create_task(task_data)
        if not task_id:
            return None
        
        solution = await self.get_task_result(task_id)
        if solution:
            return solution.get("gRecaptchaResponse")
        return None
    
    async def solve_recaptcha_v3(self, website_url: str, website_key: str, page_action: str = "verify") -> Optional[str]:
        task_data = {
            "type": "ReCaptchaV3TaskProxyLess",
            "websiteURL": website_url,
            "websiteKey": website_key,
            "pageAction": page_action
        }
        
        task_id = await self.create_task(task_data)
        if not task_id:
            return None
        
        solution = await self.get_task_result(task_id)
        if solution:
            return solution.get("gRecaptchaResponse")
        return None
    
    async def solve_hcaptcha(self, website_url: str, website_key: str, is_invisible: bool = False) -> Optional[str]:
        task_type = "HCaptchaTaskProxyLess" if not is_invisible else "HCaptchaEnterpriseTaskProxyLess"
        
        task_data = {
            "type": task_type,
            "websiteURL": website_url,
            "websiteKey": website_key,
        }
        
        task_id = await self.create_task(task_data)
        if not task_id:
            return None
        
        solution = await self.get_task_result(task_id)
        if solution:
            return solution.get("token")
        return None
    
    async def close(self):
        await self.client.aclose()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
