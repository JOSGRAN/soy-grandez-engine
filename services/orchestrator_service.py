import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
from core.task_manager import TaskManager, TaskStatus
from core.exceptions import (
    OrchestratorException, ScraperException, OTPException, 
    APIException, RetryableException
)
from core.logger import get_logger, TaskLogger
from database.repository import CredentialRepository
from database.models import PlatformType, AccountStatus
from services.laravel_api_client import LaravelAPIClient
from services.browser_manager import BrowserManager
from services.capsolver_service import CapsolverService
from services.email_otp_service import EmailOTPService
from scrapers.gosplit_scraper import GoSplitScraper
from scrapers.sharesub_scraper import ShareSubScraper
from scrapers.streaming_scraper import StreamingScraper
from config.settings import settings

logger = get_logger("orchestrator")


class OrchestratorService:
    """
    Main orchestrator that coordinates all automation components.
    Manages the complete workflow from API calls to credential updates.
    """
    
    def __init__(self):
        self.task_manager = TaskManager(max_concurrent_tasks=3)
        self.credential_repository = CredentialRepository()
        self.laravel_api = LaravelAPIClient()
        self.browser: Optional[BrowserManager] = None
        self.capsolver: Optional[CapsolverService] = None
        self.email_otp: Optional[EmailOTPService] = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize all required services."""
        if self._initialized:
            return
        
        logger.info("Initializing Orchestrator Service...")
        
        try:
            # Initialize browser manager
            self.browser = BrowserManager(headless=settings.browser_headless)
            await self.browser.start()
            
            # Initialize CAPTCHA solver if API key is available
            if settings.capsolver_api_key:
                self.capsolver = CapsolverService(api_key=settings.capsolver_api_key)
            
            # Initialize email OTP service
            try:
                self.email_otp = EmailOTPService(
                    credentials_path=settings.gmail_credentials_path,
                    token_path=settings.gmail_token_path
                )
            except Exception as e:
                logger.warning(f"Email OTP service initialization failed: {e}")
                self.email_otp = None
            
            # Authenticate with Laravel API
            await self.laravel_api.authenticate()
            
            self._initialized = True
            logger.info("Orchestrator Service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Orchestrator Service: {e}")
            raise OrchestratorException(f"Initialization failed: {e}")
    
    async def shutdown(self):
        """Cleanup resources."""
        logger.info("Shutting down Orchestrator Service...")
        
        if self.browser:
            await self.browser.close()
        
        if self.capsolver:
            await self.capsolver.close()
        
        self.task_manager.stop()
        self._initialized = False
        logger.info("Orchestrator Service shutdown complete")
    
    async def sync_expired_accounts(self) -> Dict[str, Any]:
        """
        Main sync workflow: Get expired accounts from Laravel and process them.
        
        Returns:
            Dictionary with sync results and statistics
        """
        with TaskLogger(logger, "sync_expired_accounts"):
            try:
                await self.initialize()
                
                # Step 1: Get expired accounts from Laravel API
                logger.info("Step 1: Fetching expired accounts from Laravel API...")
                expired_accounts = await self.laravel_api.get_expired_subscriptions()
                
                if not expired_accounts:
                    logger.info("No expired accounts found")
                    return {
                        "success": True,
                        "processed": 0,
                        "failed": 0,
                        "accounts": []
                    }
                
                logger.info(f"Found {len(expired_accounts)} expired accounts")
                
                # Step 2: Process each expired account
                results = []
                for account in expired_accounts:
                    result = await self.process_account(account)
                    results.append(result)
                
                # Step 3: Update Laravel with results
                logger.info("Step 3: Updating Laravel with sync results...")
                await self.update_laravel_with_results(results)
                
                # Calculate statistics
                processed = len(results)
                successful = sum(1 for r in results if r.get("success"))
                failed = processed - successful
                
                return {
                    "success": True,
                    "processed": processed,
                    "successful": successful,
                    "failed": failed,
                    "accounts": results
                }
                
            except Exception as e:
                logger.error(f"Sync failed: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "processed": 0,
                    "failed": 0
                }
    
    async def process_account(self, account: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single account through the complete automation workflow.
        
        Args:
            account: Account data from Laravel API
        
        Returns:
            Processing result dictionary
        """
        account_id = account.get('id')
        platform = account.get('platform', '').lower()
        account_name = account.get('account_name', 'Unknown')
        
        logger.info(f"Processing account: {account_name} (ID: {account_id}, Platform: {platform})")
        
        with TaskLogger(logger, f"process_account_{account_id}"):
            try:
                # Step 1: Get credentials from database
                logger.info(f"Step 1: Getting credentials for account {account_id}")
                credentials = await self.get_account_credentials(account_id, platform)
                
                if not credentials:
                    raise ScraperException(f"No credentials found for account {account_id}")
                
                # Step 2: Initialize appropriate scraper
                logger.info(f"Step 2: Initializing {platform} scraper")
                scraper = self.get_scraper(platform)
                
                if not scraper:
                    raise ScraperException(f"Unsupported platform: {platform}")
                
                # Step 3: Login to platform
                logger.info(f"Step 3: Logging into {platform}")
                login_success = await scraper.login(
                    username=credentials.get('username'),
                    password=credentials.get('password')
                )
                
                if not login_success:
                    raise AuthenticationException(f"Failed to login to {platform}")
                
                # Step 4: Navigate to account settings
                logger.info(f"Step 4: Navigating to account settings")
                await scraper.navigate_to_accounts()
                
                # Step 5: Generate new password
                logger.info(f"Step 5: Generating new password")
                new_password = self.generate_password()
                
                # Step 6: Update password in platform (with OTP handling)
                logger.info(f"Step 6: Updating password in {platform}")
                password_update_success = await scraper.update_password(account_id, new_password)
                
                if not password_update_success:
                    raise ScraperException(f"Failed to update password in {platform}")
                
                # Step 7: Update credentials in database
                logger.info(f"Step 7: Updating credentials in database")
                await self.update_credentials(account_id, new_password)
                
                # Step 8: Notify Laravel of successful update
                logger.info(f"Step 8: Notifying Laravel API")
                await self.laravel_api.update_account_password(account_id, new_password)
                
                return {
                    "success": True,
                    "account_id": account_id,
                    "platform": platform,
                    "account_name": account_name,
                    "new_password": new_password,
                    "message": "Account processed successfully"
                }
                
            except AuthenticationException as e:
                logger.error(f"Authentication failed for account {account_id}: {e}")
                return {
                    "success": False,
                    "account_id": account_id,
                    "platform": platform,
                    "error": "authentication_failed",
                    "message": str(e)
                }
                
            except OTPException as e:
                logger.error(f"OTP handling failed for account {account_id}: {e}")
                return {
                    "success": False,
                    "account_id": account_id,
                    "platform": platform,
                    "error": "otp_failed",
                    "message": str(e)
                }
                
            except ScraperException as e:
                logger.error(f"Scraper operation failed for account {account_id}: {e}")
                return {
                    "success": False,
                    "account_id": account_id,
                    "platform": platform,
                    "error": "scraper_failed",
                    "message": str(e)
                }
                
            except Exception as e:
                logger.error(f"Unexpected error processing account {account_id}: {e}")
                return {
                    "success": False,
                    "account_id": account_id,
                    "platform": platform,
                    "error": "unexpected_error",
                    "message": str(e)
                }
    
    async def get_account_credentials(self, account_id: str, platform: str) -> Optional[Dict[str, Any]]:
        """Get decrypted credentials for an account."""
        try:
            # Get credential from database
            platform_type = PlatformType(platform)
            credential = self.credential_repository.get_credential_by_id(account_id)
            
            if not credential:
                return None
            
            # TODO: Implement decryption logic here
            # For now, return as-is (should be decrypted in production)
            return {
                "username": credential.username,
                "password": credential.encrypted_password,  # This should be decrypted
                "email": credential.email,
                "api_key": credential.encrypted_api_key
            }
            
        except Exception as e:
            logger.error(f"Error getting credentials: {e}")
            return None
    
    def get_scraper(self, platform: str):
        """Get the appropriate scraper for the platform."""
        scrapers = {
            'gosplit': GoSplitScraper,
            'sharesub': ShareSubScraper,
            'netflix': lambda: StreamingScraper(self.browser, self.capsolver, self.email_otp, 'netflix'),
            'disney': lambda: StreamingScraper(self.browser, self.capsolver, self.email_otp, 'disney'),
            'disneyplus': lambda: StreamingScraper(self.browser, self.capsolver, self.email_otp, 'disney'),
        }
        
        scraper_factory = scrapers.get(platform)
        if not scraper_factory:
            return None
        
        if platform in ['netflix', 'disney', 'disneyplus']:
            return scraper_factory()
        else:
            return scraper_factory(self.browser, self.capsolver, self.email_otp)
    
    def generate_password(self, length: int = 12) -> str:
        """Generate a secure random password."""
        import secrets
        import string
        
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        password = ''.join(secrets.choice(alphabet) for _ in range(length))
        return password
    
    async def update_credentials(self, account_id: str, new_password: str) -> bool:
        """Update credentials in the database."""
        try:
            # TODO: Implement credential update with encryption
            # For now, just log the operation
            logger.info(f"Credentials updated for account {account_id}")
            return True
        except Exception as e:
            logger.error(f"Error updating credentials: {e}")
            return False
    
    async def update_laravel_with_results(self, results: List[Dict[str, Any]]) -> bool:
        """Update Laravel API with sync results."""
        try:
            for result in results:
                account_id = result.get('account_id')
                if result.get('success'):
                    # Account was processed successfully
                    await self.laravel_api.update_account_status(account_id, 'active')
                else:
                    # Account processing failed
                    await self.laravel_api.update_account_status(account_id, 'error')
            
            logger.info(f"Updated Laravel with {len(results)} account results")
            return True
        except Exception as e:
            logger.error(f"Error updating Laravel with results: {e}")
            return False
    
    async def run_scheduled_sync(self, interval_minutes: int = 60):
        """
        Run scheduled sync at regular intervals.
        
        Args:
            interval_minutes: Interval between sync runs in minutes
        """
        logger.info(f"Starting scheduled sync every {interval_minutes} minutes")
        
        while True:
            try:
                logger.info("Starting scheduled sync run...")
                result = await self.sync_expired_accounts()
                logger.info(f"Scheduled sync completed: {result}")
                
                # Wait for next interval
                await asyncio.sleep(interval_minutes * 60)
                
            except asyncio.CancelledError:
                logger.info("Scheduled sync cancelled")
                break
            except Exception as e:
                logger.error(f"Error in scheduled sync: {e}")
                # Wait before retrying
                await asyncio.sleep(60)  # Wait 1 minute before retry
    
    async def process_single_account(self, account_id: str, platform: str) -> Dict[str, Any]:
        """
        Process a single account on demand.
        
        Args:
            account_id: Account ID to process
            platform: Platform type
        
        Returns:
            Processing result
        """
        await self.initialize()
        
        account_data = {
            'id': account_id,
            'platform': platform,
            'account_name': f'Account {account_id}'
        }
        
        return await self.process_account(account_data)
