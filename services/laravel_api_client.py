import httpx
from typing import Optional, Dict, Any, List
from services.auth_service import AuthService
from config.settings import settings
import logging

logger = logging.getLogger(__name__)


class LaravelAPIClient:
    def __init__(self):
        self.base_url = settings.laravel_api_url
        self.auth_service = AuthService()
    
    async def authenticate(self) -> bool:
        token = await self.auth_service.login()
        return token is not None
    
    async def get_accounts(self, status: Optional[str] = None, platform: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            params = {}
            if status:
                params['status'] = status
            if platform:
                params['platform'] = platform
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/accounts",
                    headers=self.auth_service.get_auth_headers(),
                    params=params,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"Retrieved {len(data.get('data', []))} accounts")
                    return data.get('data', [])
                else:
                    logger.error(f"Failed to get accounts: {response.status_code} - {response.text}")
                    return []
                    
        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching accounts: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching accounts: {e}")
            return []
    
    async def get_expired_subscriptions(self) -> List[Dict[str, Any]]:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/subscriptions",
                    headers=self.auth_service.get_auth_headers(),
                    params={"status": "expired"},
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list):
                        subscriptions = data
                    elif isinstance(data, dict):
                        subscriptions = data.get('data', [])
                    else:
                        subscriptions = []
                        
                    logger.info(f"Retrieved {len(subscriptions)} expired subscriptions")
                    return subscriptions
                else:
                    logger.error(f"Failed to get expired subscriptions: {response.status_code} - {response.text}")
                    return []
                    
        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching expired subscriptions: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching expired subscriptions: {e}")
            return []
    
    async def update_account_password(self, account_id: int, new_password: str) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.put(
                    f"{self.base_url}/accounts/{account_id}/password",
                    headers=self.auth_service.get_auth_headers(),
                    json={"password": new_password},
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    logger.info(f"Successfully updated password for account {account_id}")
                    return True
                else:
                    logger.error(f"Failed to update password: {response.status_code} - {response.text}")
                    return False
                    
        except httpx.HTTPError as e:
            logger.error(f"HTTP error updating password: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error updating password: {e}")
            return False
    
    async def update_account_status(self, account_id: int, status: str) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.put(
                    f"{self.base_url}/accounts/{account_id}/status",
                    headers=self.auth_service.get_auth_headers(),
                    json={"status": status},
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    logger.info(f"Successfully updated status for account {account_id}")
                    return True
                else:
                    logger.error(f"Failed to update status: {response.status_code} - {response.text}")
                    return False
                    
        except httpx.HTTPError as e:
            logger.error(f"HTTP error updating status: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error updating status: {e}")
            return False
    
    async def send_account_update(self, account_data: Dict[str, Any]) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/accounts/sync",
                    headers=self.auth_service.get_auth_headers(),
                    json=account_data,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    logger.info(f"Successfully synced account data")
                    return True
                else:
                    logger.error(f"Failed to sync account: {response.status_code} - {response.text}")
                    return False
                    
        except httpx.HTTPError as e:
            logger.error(f"HTTP error syncing account: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error syncing account: {e}")
            return False