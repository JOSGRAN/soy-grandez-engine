import httpx
from typing import Optional, Dict, Any
from config.settings import settings
import logging

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self):
        self.base_url = settings.laravel_api_url
        self.token: Optional[str] = settings.laravel_api_token
        self.email = settings.laravel_api_email
        self.password = settings.laravel_api_password
    
    async def login(self) -> Optional[str]:
        if self.token:
            logger.info("Using pre-configured token")
            return self.token
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/login",
                    json={
                        "email": self.email,
                        "password": self.password
                    },
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    self.token = data.get('token')
                    logger.info("Authentication successful")
                    return self.token
                else:
                    logger.error(f"Authentication failed: {response.status_code} - {response.text}")
                    return None
                    
        except httpx.HTTPError as e:
            logger.error(f"HTTP error during authentication: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during authentication: {e}")
            return None
    
    def get_auth_headers(self) -> Dict[str, str]:
        if not self.token:
            raise ValueError("No authentication token available. Please login first.")
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
    def is_authenticated(self) -> bool:
        return self.token is not None
