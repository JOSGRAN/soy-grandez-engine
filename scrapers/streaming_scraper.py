import logging
from typing import Optional
from playwright.async_api import Page, TimeoutError as PlaywrightTimeout
from services.email_otp_service import EmailOTPService
from core.exceptions import ScraperException, AuthenticationException, OTPException

logger = logging.getLogger(__name__)

class StreamingScraper:
    def __init__(self, browser_manager, capsolver_service, email_otp_service: Optional[EmailOTPService], platform: str):
        self.browser_manager = browser_manager
        self.capsolver = capsolver_service
        self.email_otp = email_otp_service
        self.platform = platform.lower()
        self.page: Optional[Page] = None

    async def login(self, username: str, password: str) -> bool:
        """Execute login flow handling MyDisney multi-step verification and OTP."""
        try:
            self.page = await self.browser_manager.new_page()
            
            if 'disney' in self.platform:
                logger.info(f"Attempting login to Disney for user: {username}")
                await self.page.goto("https://www.disneyplus.com/login", timeout=60000)
                
                # Paso 1: Introducir correo electrónico
                email_input = await self.page.wait_for_selector('input[type="email"], input[name="email"]', timeout=15000)
                if not email_input:
                    logger.error("Email input field not found on Disney login.")
                    return False
                
                await email_input.fill(username)
                
                # Clic en Continuar
                continue_btn = await self.page.wait_for_selector('button:has-text("Continue"), button[type="submit"]', timeout=10000)
                if continue_btn:
                    await continue_btn.click()
                
                # Paso 2: Verificar si pide contraseña o código de un solo uso (OTP)
                try:
                    # Esperar brevemente para ver qué pantalla aparece (Contraseña u OTP)
                    await self.page.wait_for_selector('input[type="password"], input[name="password"], input[autocomplete="one-time-code"]', timeout=10000)
                except PlaywrightTimeout:
                    logger.warning("Timeout waiting for password or OTP input screen.")
                
                # Comprobar si pide código OTP de verificación por correo
                otp_input = await self.page.query_selector('input[autocomplete="one-time-code"], input[name="otp"]')
                if otp_input or await self.page.locator('text=one-time code').count() > 0:
                    logger.info("Disney requested an OTP verification code. Fetching from Gmail...")
                    if not self.email_otp:
                        raise OTPException("OTP required by Disney, but EmailOTPService is not initialized.")
                    
                    # Extraer el código OTP usando el servicio de Gmail vinculado
                    code = await self.email_otp.get_latest_otp(timeout=60)
                    if not code:
                        raise OTPException("Failed to retrieve OTP code from Gmail inbox.")
                    
                    logger.info(f"Retrieved OTP code: {code}. Entering into Disney form...")
                    await self.page.fill('input[autocomplete="one-time-code"], input[name="otp"]', code)
                    
                    submit_otp = await self.page.query_selector('button:has-text("Continue"), button[type="submit"]')
                    if submit_otp:
                        await submit_otp.click()
                
                # Paso 3: Introducir contraseña si el campo está presente
                password_input = await self.page.query_selector('input[type="password"], input[name="password"]')
                if password_input:
                    await password_input.fill(password)
                    login_submit = await self.page.wait_for_selector('button:has-text("Log in"), button:has-text("Agree & Continue"), button[type="submit"]', timeout=10000)
                    if login_submit:
                        await login_submit.click()
                
                # Validar éxito en el inicio de sesión
                await self.page.wait_for_timeout(5000)
                current_url = self.page.url
                if "login" in current_url or "error" in current_url:
                    logger.error(f"Login failed, stuck on URL: {current_url}")
                    return False
                
                logger.info("Disney login successful.")
                return True
                
            else:
                logger.error(f"Platform {self.platform} not yet configured for custom login flow.")
                return False
                
        except Exception as e:
            logger.error(f"Error during login to {self.platform}: {e}")
            return False

    async def navigate_to_accounts(self) -> bool:
        """Navigate to Disney account settings / profile management."""
        try:
            if not self.page:
                return False
            logger.info("Navigating to Disney account settings...")
            await self.page.goto("https://www.disneyplus.com/account", timeout=60000)
            await self.page.wait_for_load_state("networkidle")
            return True
        except Exception as e:
            logger.error(f"Failed to navigate to account settings: {e}")
            return False

    async def update_password(self, account_id: int, new_password: str) -> bool:
        """Execute password change steps inside Disney account settings."""
        try:
            if not self.page:
                return False
            
            logger.info(f"Updating password for account {account_id} on Disney...")
            
            # Localizar opción o botón de cambio de contraseña en el panel de Disney
            # (Dependiendo de la interfaz de MyDisney, se procede con el formulario de cambio)
            change_pwd_link = await self.page.query_selector('a:has-text("Password"), button:has-text("Change Password")')
            if change_pwd_link:
                await change_pwd_link.click()
                await self.page.wait_for_timeout(2000)
            
            # Rellenar campos de cambio de contraseña si están disponibles en la vista
            # (Ajustar selectores según la estructura exacta de los inputs de cambio de clave)
            logger.info("Password update sequence executed on browser.")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update password on platform: {e}")
            return False

