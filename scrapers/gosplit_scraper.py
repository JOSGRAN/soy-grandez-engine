from typing import Dict, Any, Optional
from scrapers.base_scraper import BaseScraper
import logging

logger = logging.getLogger(__name__)


class GoSplitScraper(BaseScraper):
    def __init__(self, browser_manager, capsolver_service=None, email_otp_service=None):
        super().__init__(browser_manager, capsolver_service, email_otp_service)
        self.base_url = "https://gosplit.com"
        self.login_url = f"{self.base_url}/login"
        self.dashboard_url = f"{self.base_url}/dashboard"
        self.accounts_url = f"{self.base_url}/accounts"
        self.otp_sender = "gosplit.com"
    
    async def login(self, username: str, password: str) -> bool:
        try:
            logger.info(f"Attempting login to GoSplit for user: {username}")
            
            await self.browser.navigate(self.login_url)
            await self.browser.wait_for_selector('input[name="email"]', timeout=10000)
            
            # Fill login form
            await self.browser.fill('input[name="email"]', username)
            await self.browser.wait(500)
            await self.browser.fill('input[name="password"]', password)
            await self.browser.wait(500)
            
            # Check for captcha and solve if present
            await self.solve_captcha_if_present("turnstile")
            
            # Submit login
            await self.browser.click('button[type="submit"]')
            await self.wait_for_page_load()
            
            # Verify successful login
            current_url = self.browser.page.url
            if "dashboard" in current_url or "login" not in current_url:
                logger.info("GoSplit login successful")
                await self.take_screenshot("login_success")
                return True
            else:
                logger.error("GoSplit login failed - still on login page")
                await self.take_screenshot("login_failed")
                return False
                
        except Exception as e:
            logger.error(f"Error during GoSplit login: {e}")
            await self.take_screenshot("login_error")
            return False
    
    async def navigate_to_accounts(self) -> bool:
        try:
            logger.info("Navigating to GoSplit accounts section")
            
            await self.browser.navigate(self.accounts_url)
            await self.wait_for_page_load()
            
            # Wait for accounts table to load
            await self.browser.wait_for_selector('table, .accounts-list, .account-card', timeout=10000)
            
            logger.info("Successfully navigated to accounts section")
            await self.take_screenshot("accounts_page")
            return True
            
        except Exception as e:
            logger.error(f"Error navigating to accounts: {e}")
            return False
    
    async def get_account_status(self, account_id: str) -> Dict[str, Any]:
        try:
            logger.info(f"Getting status for GoSplit account: {account_id}")
            
            # Navigate to specific account page
            account_url = f"{self.accounts_url}/{account_id}"
            await self.browser.navigate(account_url)
            await self.wait_for_page_load()
            
            # Extract account information
            status = {
                "account_id": account_id,
                "platform": "gosplit",
                "status": "unknown",
                "subscription_end": None,
                "is_active": False,
                "profile_name": None
            }
            
            # Try to extract status from common selectors
            status_selectors = [
                '.status', '.account-status', '[data-status]', '.subscription-status'
            ]
            
            for selector in status_selectors:
                status_text = await self.browser.get_text(selector)
                if status_text:
                    status["status"] = status_text.lower()
                    status["is_active"] = "active" in status_text.lower()
                    break
            
            # Try to extract subscription end date
            date_selectors = [
                '.end-date', '.subscription-end', '[data-end-date]', '.renewal-date'
            ]
            
            for selector in date_selectors:
                date_text = await self.browser.get_text(selector)
                if date_text:
                    status["subscription_end"] = date_text
                    break
            
            # Try to extract profile name
            name_selectors = [
                '.profile-name', '.account-name', 'h1, h2', '[data-name]'
            ]
            
            for selector in name_selectors:
                name_text = await self.browser.get_text(selector)
                if name_text:
                    status["profile_name"] = name_text
                    break
            
            logger.info(f"Account status retrieved: {status}")
            return status
            
        except Exception as e:
            logger.error(f"Error getting account status: {e}")
            return {"account_id": account_id, "platform": "gosplit", "error": str(e)}
    
    async def update_password(self, account_id: str, new_password: str) -> bool:
        try:
            logger.info(f"Updating password for GoSplit account: {account_id}")
            
            # Navigate to account settings
            account_url = f"{self.accounts_url}/{account_id}/settings"
            await self.browser.navigate(account_url)
            await self.wait_for_page_load()
            
            # Find password change form
            await self.browser.wait_for_selector('input[type="password"], input[name="password"]', timeout=10000)
            
            # Fill new password
            await self.browser.fill('input[name="new_password"], input[type="password"]:first-of-type', new_password)
            await self.browser.wait(500)
            
            # Confirm password
            await self.browser.fill('input[name="confirm_password"], input[type="password"]:nth-of-type(2)', new_password)
            await self.browser.wait(500)
            
            # Submit password change
            await self.browser.click('button[type="submit"], .save-password-btn, .update-btn')
            await self.wait_for_page_load()
            
            # Verify success
            success_message = await self.browser.get_text('.success-message, .alert-success, .notification-success')
            if success_message and "success" in success_message.lower():
                logger.info("Password updated successfully")
                await self.take_screenshot("password_update_success")
                return True
            else:
                logger.error("Password update failed")
                await self.take_screenshot("password_update_failed")
                return False
                
        except Exception as e:
            logger.error(f"Error updating password: {e}")
            await self.take_screenshot("password_update_error")
            return False
    
    async def update_pin(self, account_id: str, new_pin: str) -> bool:
        try:
            logger.info(f"Updating PIN for GoSplit account: {account_id}")
            
            # Navigate to PIN settings
            account_url = f"{self.accounts_url}/{account_id}/pin"
            await self.browser.navigate(account_url)
            await self.wait_for_page_load()
            
            # Find PIN change form
            await self.browser.wait_for_selector('input[name="pin"], input[type="text"][maxlength="4"]', timeout=10000)
            
            # Fill new PIN
            await self.browser.fill('input[name="new_pin"], input[type="text"]:first-of-type', new_pin)
            await self.browser.wait(500)
            
            # Confirm PIN
            await self.browser.fill('input[name="confirm_pin"], input[type="text"]:nth-of-type(2)', new_pin)
            await self.browser.wait(500)
            
            # Submit PIN change
            await self.browser.click('button[type="submit"], .save-pin-btn, .update-btn')
            await self.wait_for_page_load()
            
            # Verify success
            success_message = await self.browser.get_text('.success-message, .alert-success, .notification-success')
            if success_message and "success" in success_message.lower():
                logger.info("PIN updated successfully")
                await self.take_screenshot("pin_update_success")
                return True
            else:
                logger.error("PIN update failed")
                await self.take_screenshot("pin_update_failed")
                return False
                
        except Exception as e:
            logger.error(f"Error updating PIN: {e}")
            await self.take_screenshot("pin_update_error")
            return False
    
    async def get_all_accounts(self) -> list:
        try:
            logger.info("Getting all GoSplit accounts")
            
            await self.navigate_to_accounts()
            
            accounts = []
            account_rows = await self.browser.page.query_selector_all('tr.account-row, .account-card, .account-item')
            
            for row in account_rows:
                try:
                    account_id = await row.get_attribute("data-id") or await row.get_attribute("id")
                    account_name = await row.query_selector('.account-name, .name, td:first-child')
                    
                    if account_name:
                        name_text = await account_name.inner_text()
                    else:
                        name_text = "Unknown"
                    
                    accounts.append({
                        "id": account_id,
                        "name": name_text,
                        "platform": "gosplit"
                    })
                except Exception as e:
                    logger.error(f"Error parsing account row: {e}")
                    continue
            
            logger.info(f"Found {len(accounts)} accounts")
            return accounts
            
        except Exception as e:
            logger.error(f"Error getting all accounts: {e}")
            return []
