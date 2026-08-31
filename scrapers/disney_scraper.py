import secrets
import string
import asyncio
import logging
from typing import Dict, Any, Optional
from scrapers.base_scraper import BaseScraper
from core.exceptions import (
    ScraperException,
    AuthenticationException,
    OTPException,
    TimeoutException,
)

logger = logging.getLogger(__name__)


class DisneyScraper(BaseScraper):
    """
    Automatización de rotación de credenciales y perfiles en Disney+

    Constructor recibe, en primer lugar, los datos de la cuenta (obligatorios
    para su uso directo), y luego los servicios de soporte siguiendo la
    interfaz BaseScraper.

    Args:
        username: Correo electrónico / usuario de la cuenta Disney+
        password: Contraseña maestra actual de Disney+
        otp_password: Contraseña de aplicación de Google de 16 caracteres
                      para acceder por IMAP al buzón Gmail de la cuenta.
        profile_name: Nombre del perfil que hay que actualizar con PIN nuevo.
        profile_pin: Nuevo PIN numérico de 4-6 dígitos para el perfil.
        browser_manager: Instancia iniciada de BrowserManager.
        capsolver_service: (opcional) Servicio Capsolver para CAPTCHAs.
        email_otp_service: (opcional) Instancia de EmailOTPService; si no
                           se proporciona, se instancia internamente.
    """

    BASE_URL = "https://www.disneyplus.com"
    LOGIN_URL = "https://www.disneyplus.com/login"
    ACCOUNT_URL = "https://www.disneyplus.com/account"
    SECURITY_URL = "https://www.disneyplus.com/account/security"
    DEVICES_URL = "https://www.disneyplus.com/account/devices"
    PROFILES_URL = "https://www.disneyplus.com/profiles"

    LOGIN_TIMEOUT_MS = 60_000
    STEP_TIMEOUT_MS = 20_000
    NAV_TIMEOUT_MS = 45_000

    def __init__(
        self,
        username: str,
        password: str,
        otp_password: str,
        profile_name: str,
        profile_pin: str,
        browser_manager=None,
        capsolver_service=None,
        email_otp_service=None,
    ):
        super().__init__(browser_manager, capsolver_service, email_otp_service)

        if not browser_manager:
            raise ScraperException(
                "DisneyScraper requiere una instancia iniciada de BrowserManager"
            )
        if not username or not password:
            raise ScraperException(
                "DisneyScraper requiere username (email) y password"
            )

        self.username = username
        self.password = password
        self.otp_password = otp_password
        self.profile_name = profile_name
        self.profile_pin = str(profile_pin)
        self.new_password: Optional[str] = None
        self._logged_in: bool = False

        if not self.email_otp:
            from services.email_otp_service import EmailOTPService

            self.email_otp = EmailOTPService()

        self.platform_name = "DisneyScraper"

    # =========================================================================
    # Helpers utilitarios
    # =========================================================================

    @staticmethod
    def generate_secure_password(length: int = 20) -> str:
        """
        Genera una contraseña segura y compatible con Disney+:
            - Entre 12 y 32 caracteres (default 20)
            - Al menos una mayúscula, una minúscula, un dígito y un símbolo
            - Símbolos permitidos por Disney+ (- _ . ! @ # $ % ^ & *)
        """
        if length < 12:
            length = 12
        if length > 32:
            length = 32

        allowed_symbols = "-_.!@#$%^&*"
        alphabet = string.ascii_letters + string.digits + allowed_symbols
        rng = secrets.SystemRandom()

        while True:
            candidate = "".join(rng.choice(alphabet) for _ in range(length))
            has_upper = any(c.isupper() for c in candidate)
            has_lower = any(c.islower() for c in candidate)
            has_digit = any(c.isdigit() for c in candidate)
            has_symbol = any(c in allowed_symbols for c in candidate)
            if all([has_upper, has_lower, has_digit, has_symbol]):
                return candidate

    async def _safe_click_any(self, selectors, timeout_ms: int = 15_000) -> bool:
        """
        Intenta hacer click en cualquiera de los selectores proporcionados,
        probándolos en orden. Retorna True si alguno tuvo éxito.
        """
        page = self.browser.page
        for selector in selectors:
            try:
                locator = page.locator(selector).first
                if await locator.is_visible(timeout=min(2000, timeout_ms)):
                    await locator.click(timeout=timeout_ms, force=False)
                    await asyncio.sleep(0.8)
                    return True
            except Exception:
                continue
        for selector in selectors:
            try:
                await page.click(selector, timeout=timeout_ms, force=True)
                await asyncio.sleep(0.8)
                return True
            except Exception:
                continue
        return False

    async def _safe_fill_any(self, selectors, value: str, timeout_ms: int = 10_000) -> bool:
        """Rellena el primer input visible/cargado de la lista de selectores."""
        page = self.browser.page
        for selector in selectors:
            try:
                locator = page.locator(selector).first
                if await locator.is_visible(timeout=min(2000, timeout_ms)):
                    await locator.fill(value, timeout=timeout_ms)
                    await asyncio.sleep(0.3)
                    return True
            except Exception:
                continue
        for selector in selectors:
            try:
                el = await page.query_selector(selector)
                if el is not None:
                    await el.fill(value, timeout=timeout_ms)
                    await asyncio.sleep(0.3)
                    return True
            except Exception:
                continue
        return False

    async def _is_logged_in_dom(self) -> bool:
        """Infiere si la sesión está iniciada por URL/DOM."""
        page = self.browser.page
        current_url = page.url
        if any(x in current_url for x in ["/home", "/welcome", "/account", "/profiles"]):
            return True
        profile_selectors = [
            "[data-testid='profile-selector']",
            ".profile-selector",
            "[data-profile-id]",
            "nav button svg",
            "a[href*='/profile']",
        ]
        for sel in profile_selectors:
            try:
                if await page.locator(sel).first.count() > 0:
                    return True
            except Exception:
                continue
        return False

    # =========================================================================
    # 1. Inicio de sesión
    # =========================================================================

    async def login(self, username: Optional[str] = None, password: Optional[str] = None) -> bool:
        """
        Ejecuta el flujo completo de autenticación en Disney+:
            1. Navega a /login
            2. Ingresa el correo (username)
            3. Detecta si aparece contraseña o OTP:
                - Si hay campo de password → lo rellena
                - Si hay OTP (one-time code) → consulta Gmail por IMAP con
                  otp_password y lo introduce (timeout ≤ 30s)
            4. Continúa al portal de selección de perfiles / home
            5. Resuelve Cloudflare Turnstile si aparece (con Capsolver)
        """
        user = username or self.username
        pwd = password or self.password

        logger.info(f"[DisneyScraper] Iniciando login para {user}")

        try:
            await self.browser.navigate(self.LOGIN_URL)
            try:
                await self.browser.page.wait_for_load_state("domcontentloaded", timeout=self.NAV_TIMEOUT_MS)
            except Exception:
                pass

            await self.solve_captcha_if_present("turnstile")

            # --- Paso 1: email ------------------------------------------------
            email_selectors = [
                'input[type="email"]',
                'input[name="email"]',
                'input[name="emailInput"]',
                'input[autocomplete="email"]',
                'input[placeholder*="email" i]',
                'input[placeholder*="correo" i]',
            ]
            filled = await self._safe_fill_any(email_selectors, user, timeout_ms=self.STEP_TIMEOUT_MS)
            if not filled:
                logger.error("[DisneyScraper] No se encontró el input de email en login")
                await self.take_screenshot("login_no_email_input")
                return False

            continue_btns = [
                'button:has-text("Continue")',
                'button:has-text("Continuar")',
                'button[type="submit"]',
                'button[data-testid*="continue" i]',
                'button[aria-label*="Continue" i]',
            ]
            clicked = await self._safe_click_any(continue_btns, timeout_ms=self.STEP_TIMEOUT_MS)
            if not clicked:
                logger.warning("[DisneyScraper] No se pudo hacer clic en Continue; intentando submit con Enter")
                try:
                    await self.browser.page.keyboard.press("Enter")
                    await asyncio.sleep(1.5)
                except Exception:
                    pass

            await asyncio.sleep(2.5)
            await self.solve_captcha_if_present("turnstile")

            # --- Paso 2: detectar pantalla password vs OTP -------------------
            pwd_selectors = [
                'input[type="password"]',
                'input[name="password"]',
                'input[name="passwordInput"]',
                'input[autocomplete="current-password"]',
            ]
            otp_selectors = [
                'input[autocomplete="one-time-code"]',
                'input[name="otp"]',
                'input[name="otpCode"]',
                'input[name="verificationCode"]',
                'input[data-testid*="otp" i]',
                'input[data-testid*="code" i]',
                'input[aria-label*="code" i]',
                'input[aria-label*="OTP" i]',
                'input[type="text"][inputmode="numeric"]',
            ]

            wait_for = pwd_selectors + otp_selectors
            detected_password = False
            detected_otp = False
            try:
                await self.browser.page.wait_for_selector(
                    ", ".join(wait_for),
                    timeout=self.LOGIN_TIMEOUT_MS,
                )
            except Exception:
                logger.warning(
                    "[DisneyScraper] Timeout esperando inputs de password/OTP; "
                    "se intenta detectar de todos modos"
                )

            for sel in pwd_selectors:
                el = await self.browser.page.query_selector(sel)
                if el and await el.is_visible():
                    detected_password = True
                    break
            for sel in otp_selectors:
                el = await self.browser.page.query_selector(sel)
                if el and await el.is_visible():
                    detected_otp = True
                    break

            # --- Paso 3a: OTP (si aparece antes que password) ----------------
            if detected_otp and not detected_password:
                logger.info("[DisneyScraper] Disney+ solicitó OTP por email. Consultando IMAP...")
                success = await self._enter_disney_otp_via_imap(otp_selectors)
                if not success:
                    await self.take_screenshot("login_otp_failed")
                    return False
                await self.solve_captcha_if_present("turnstile")
                await asyncio.sleep(2.0)
                for sel in pwd_selectors:
                    el = await self.browser.page.query_selector(sel)
                    if el and await el.is_visible():
                        detected_password = True
                        break

            # --- Paso 3b: contraseña (ahora sí está visible) -----------------
            if detected_password:
                filled_pwd = await self._safe_fill_any(pwd_selectors, pwd, timeout_ms=self.STEP_TIMEOUT_MS)
                if not filled_pwd:
                    logger.error("[DisneyScraper] No se pudo rellenar el campo de contraseña")
                    await self.take_screenshot("login_no_password_input")
                    return False

                login_btns = [
                    'button:has-text("Log in")',
                    'button:has-text("Login")',
                    'button:has-text("Iniciar sesión")',
                    'button:has-text("Agree & Continue")',
                    'button:has-text("Continuar")',
                    'button[type="submit"]',
                ]
                clicked_login = await self._safe_click_any(login_btns, timeout_ms=self.STEP_TIMEOUT_MS)
                if not clicked_login:
                    try:
                        await self.browser.page.keyboard.press("Enter")
                    except Exception:
                        pass

                await asyncio.sleep(2.5)
                await self.solve_captcha_if_present("turnstile")

            # --- Paso 4: detectar si pidió OTP *después* de password ---------
            still_needs_otp = False
            for sel in otp_selectors:
                el = await self.browser.page.query_selector(sel)
                if el and await el.is_visible():
                    still_needs_otp = True
                    break
            prompt_text_otp = await self.browser.page.locator(
                "text=/one-time|one time|verification code|código|código de verificación/i"
            ).count()
            if prompt_text_otp > 0:
                still_needs_otp = True

            if still_needs_otp:
                logger.info("[DisneyScraper] Disney+ solicitó OTP DESPUÉS del password. Reintentando IMAP...")
                if not await self._enter_disney_otp_via_imap(otp_selectors):
                    await self.take_screenshot("login_second_otp_failed")
                    return False
                await asyncio.sleep(2.0)

            # --- Paso 5: validar login exitoso -------------------------------
            try:
                await self.browser.page.wait_for_load_state("domcontentloaded", timeout=15_000)
            except Exception:
                pass

            for _ in range(6):
                if await self._is_logged_in_dom():
                    self._logged_in = True
                    logger.info(f"[DisneyScraper] Login exitoso para {user}")
                    await self.take_screenshot("login_success")
                    return True
                await asyncio.sleep(1.5)

            current_url = self.browser.page.url
            if "login" in current_url.lower():
                logger.error(f"[DisneyScraper] Login fallido. Sigue en URL: {current_url}")
                await self.take_screenshot("login_failed_stuck")
                return False

            self._logged_in = True
            await self.take_screenshot("login_success_late")
            return True

        except AuthenticationException:
            raise
        except OTPException:
            raise
        except Exception as e:
            logger.exception(f"[DisneyScraper] Error excepción en login: {e}")
            await self.take_screenshot("login_exception")
            return False

    async def _enter_disney_otp_via_imap(self, otp_selectors) -> bool:
        """
        Usa EmailOTPService.get_disney_otp_via_imap con el email de la cuenta
        y el otp_password (app password Google de 16 dígitos). Si hay éxito
        introduce el código de 6 dígitos y pulsa Continue/Submit.
        """
        if not self.email_otp:
            raise OTPException(
                "[DisneyScraper] Se requirió OTP pero no hay EmailOTPService disponible"
            )

        # Polling IMAP con timeout máximo de 30s según requisito
        otp_data = self.email_otp.get_disney_otp_via_imap(
            email_address=self.username,
            app_password=self.otp_password,
            timeout_seconds=30,
            poll_interval=3,
            minutes_ago=5,
        )

        if not otp_data or not otp_data.get("code"):
            logger.error("[DisneyScraper] No se pudo recuperar OTP 6-dígitos vía IMAP en ≤30s")
            return False

        code = otp_data["code"]
        logger.info(
            f"[DisneyScraper] OTP recuperado ({otp_data.get('via','IMAP')}): {code}. "
            f"Introduciendo en formulario..."
        )

        filled_code = False
        # Intento 1: input simple
        for sel in otp_selectors:
            try:
                locator = self.browser.page.locator(sel).first
                if await locator.is_visible(timeout=1500):
                    await locator.fill(code, timeout=8000)
                    filled_code = True
                    break
            except Exception:
                continue

        # Intento 2: 6 inputs individuales (split input)
        if not filled_code:
            split_inputs = await self.browser.page.query_selector_all(
                "input[type='text'][maxlength='1'], input[type='number'][maxlength='1'], input[aria-label*='digit' i]"
            )
            if split_inputs and len(split_inputs) >= 6 and len(code) == 6:
                for idx, inp in enumerate(split_inputs[:6]):
                    try:
                        await inp.fill(code[idx])
                        await asyncio.sleep(0.1)
                    except Exception:
                        pass
                filled_code = True

        if not filled_code:
            logger.error("[DisneyScraper] No se pudo introducir el código OTP en los inputs")
            return False

        logger.info("[DisneyScraper] OTP introducido; pulsando continuar...")
        otp_submit_btns = [
            'button:has-text("Continue")',
            'button:has-text("Continuar")',
            'button:has-text("Verify")',
            'button:has-text("Verificar")',
            'button[type="submit"]',
        ]
        await self._safe_click_any(otp_submit_btns, timeout_ms=12_000)
        return True

    # =========================================================================
    # 2. Revocación de dispositivos (cerrar sesión en todos)
    # =========================================================================

    async def navigate_to_accounts(self) -> bool:
        """Implementación abstracta BaseScraper: navega a /account."""
        try:
            await self.browser.navigate(self.ACCOUNT_URL)
            try:
                await self.browser.page.wait_for_load_state("domcontentloaded", timeout=self.NAV_TIMEOUT_MS)
            except Exception:
                pass
            return True
        except Exception as e:
            logger.error(f"[DisneyScraper] navigate_to_accounts error: {e}")
            return False

    async def revoke_devices(self) -> bool:
        """
        Navega a la sección de dispositivos y ejecuta "Cerrar sesión en TODOS
        los dispositivos". Si no existe ese botón explícito, intenta revocar
        cada dispositivo de forma individual.
        """
        logger.info("[DisneyScraper] Revocando (logout) todos los dispositivos...")
        if not self._logged_in:
            ok = await self.login()
            if not ok:
                raise AuthenticationException("[DisneyScraper] No autenticado para revocar dispositivos")

        try:
            await self.browser.navigate(self.DEVICES_URL)
            try:
                await self.browser.page.wait_for_load_state("domcontentloaded", timeout=self.NAV_TIMEOUT_MS)
            except Exception:
                pass
            await asyncio.sleep(1.5)
        except Exception as e:
            logger.warning(f"[DisneyScraper] No se pudo navegar a /account/devices: {e}")
            try:
                await self.browser.navigate(self.ACCOUNT_URL)
                await asyncio.sleep(2)
            except Exception:
                pass

        # Botón global "Cerrar sesión en todos los dispositivos"
        global_logout_btns = [
            'button:has-text("Log out of all devices")',
            'button:has-text("Log Out Of All Devices")',
            'button:has-text("Cerrar sesión en todos")',
            'button:has-text("Cerrar sesión en todos los dispositivos")',
            'button:has-text("Sign out of all devices")',
            'button:has-text("Cerrar todas las sesiones")',
            'button[data-testid*="logout-all" i]',
            'a:has-text("Log out of all devices")',
            'a:has-text("Cerrar sesión en todos")',
        ]
        clicked = await self._safe_click_any(global_logout_btns, timeout_ms=12_000)
        if clicked:
            logger.info("[DisneyScraper] Click en botón global de revocación. Confirmando modal...")
            await asyncio.sleep(1.0)
            confirm_btns = [
                'button:has-text("Log out")',
                'button:has-text("Logout")',
                'button:has-text("Confirm")',
                'button:has-text("Confirmar")',
                'button:has-text("Sí")',
                'button:has-text("Yes")',
                'button:has-text("Continuar")',
                'button:has-text("Continue")',
            ]
            await self._safe_click_any(confirm_btns, timeout_ms=10_000)
            await asyncio.sleep(2.0)
            await self.take_screenshot("revoke_devices_global_done")
            logger.info("[DisneyScraper] Revocación global de dispositivos ejecutada")
            return True

        # Fallback: revocar cada dispositivo individualmente
        logger.info(
            "[DisneyScraper] Botón global no encontrado; intentando revocación individual"
        )
        try:
            rows = await self.browser.page.query_selector_all(
                "[data-testid*='device' i], .device-card, .device-item, li.device"
            )
        except Exception:
            rows = []

        if not rows:
            rows = await self.browser.page.query_selector_all("button:has-text('Remove'), button:has-text('Eliminar'), button:has-text('Sign out')")

        revoked = 0
        for idx in range(min(len(rows), 30)):
            try:
                row = await self.browser.page.query_selector_all(
                    "[data-testid*='device' i], .device-card, .device-item, li.device"
                )
                if not row or idx >= len(row):
                    row = await self.browser.page.query_selector_all(
                        "button:has-text('Remove'), button:has-text('Eliminar'), button:has-text('Sign out')"
                    )
                    if idx >= len(row):
                        break
                row_btns = [
                    "button:has-text('Sign out')",
                    "button:has-text('Remove')",
                    "button:has-text('Cerrar sesión')",
                    "button:has-text('Eliminar')",
                    "button[aria-label*='remove' i]",
                    "button[aria-label*='sign out' i]",
                ]
                try:
                    await row[idx].scroll_into_view_if_needed(timeout=3000)
                except Exception:
                    pass
                found = False
                for sel in row_btns:
                    try:
                        b = await row[idx].query_selector(sel)
                        if b and await b.is_visible():
                            await b.click(force=True)
                            found = True
                            break
                    except Exception:
                        continue
                if found:
                    revoked += 1
                    await asyncio.sleep(0.7)
                    confirm_btns = [
                        'button:has-text("Confirm")',
                        'button:has-text("Confirmar")',
                        'button:has-text("Yes")',
                        'button:has-text("Sí")',
                        'button:has-text("Remove")',
                        'button:has-text("Eliminar")',
                    ]
                    try:
                        for csel in confirm_btns:
                            cbtn = await self.browser.page.query_selector(csel)
                            if cbtn and await cbtn.is_visible(timeout=1500):
                                await cbtn.click()
                                await asyncio.sleep(0.5)
                                break
                    except Exception:
                        pass
            except Exception as e:
                logger.warning(f"[DisneyScraper] Error al revocar dispositivo #{idx}: {e}")
                continue

        logger.info(f"[DisneyScraper] Revocación individual: {revoked} dispositivos procesados")
        await self.take_screenshot(f"revoke_devices_individual_{revoked}_done")
        return True

    async def get_account_status(self, account_id: str) -> Dict[str, Any]:
        """Implementación de la interfaz BaseScraper (DisneyScraper)."""
        return {
            "account_id": account_id,
            "platform": "disneyplus",
            "username": self.username,
            "profile_name": self.profile_name,
            "logged_in": self._logged_in,
        }

    # =========================================================================
    # 3. Rotación de contraseña maestra
    # =========================================================================

    async def update_password(self, account_id: str, new_password: str) -> bool:
        """Alias para rotate_password (impl. de la interfaz BaseScraper)."""
        return await self.rotate_password(new_password)

    async def rotate_password(self, force_new_password: Optional[str] = None) -> bool:
        """
        Navega a /account/security, localiza el formulario de cambio de
        contraseña, genera una contraseña nueva segura (o usa la pasada) y
        la actualiza. Almacena el resultado en self.new_password.
        """
        logger.info("[DisneyScraper] Iniciando rotación de contraseña maestra...")
        if not self._logged_in:
            ok = await self.login()
            if not ok:
                raise AuthenticationException("[DisneyScraper] No autenticado para rotar password")

        chosen_pwd = force_new_password or self.generate_secure_password(20)
        old_password = self.password

        try:
            await self.browser.navigate(self.SECURITY_URL)
            try:
                await self.browser.page.wait_for_load_state("domcontentloaded", timeout=self.NAV_TIMEOUT_MS)
            except Exception:
                pass
            await asyncio.sleep(2.0)
        except Exception as e:
            logger.warning(f"[DisneyScraper] No se pudo navegar a /account/security: {e}")
            try:
                await self.browser.navigate(self.ACCOUNT_URL)
                await asyncio.sleep(2.0)
                pwd_links = [
                    'a:has-text("Password")',
                    'a:has-text("Contraseña")',
                    'a:has-text("Change password")',
                    'button:has-text("Password")',
                    'button:has-text("Contraseña")',
                    '[data-testid*="change-password" i]',
                ]
                await self._safe_click_any(pwd_links, timeout_ms=10_000)
                await asyncio.sleep(1.5)
            except Exception:
                pass

        old_pwd_selectors = [
            'input[name="oldPassword"]',
            'input[name="current-password"]',
            'input[autocomplete="current-password"]',
            'input[placeholder*="current" i]',
            'input[placeholder*="actual" i]',
        ]
        new_pwd_selectors = [
            'input[name="newPassword"]',
            'input[name="password"]',
            'input[autocomplete="new-password"]',
            'input[placeholder*="new" i]',
            'input[placeholder*="nueva" i]',
        ]
        confirm_pwd_selectors = [
            'input[name="confirmPassword"]',
            'input[name="password_confirm"]',
            'input[name="verifyPassword"]',
            'input[placeholder*="confirm" i]',
            'input[placeholder*="verificar" i]',
        ]

        filled_old = await self._safe_fill_any(old_pwd_selectors, old_password, timeout_ms=10_000)
        filled_new = await self._safe_fill_any(new_pwd_selectors, chosen_pwd, timeout_ms=10_000)
        filled_conf = await self._safe_fill_any(confirm_pwd_selectors, chosen_pwd, timeout_ms=10_000)

        if not (filled_new and filled_conf):
            # Intentar buscando inputs tipo password en orden: viejo -> nuevo -> confirm
            pwd_inputs = await self.browser.page.query_selector_all('input[type="password"]')
            if len(pwd_inputs) >= 2:
                try:
                    if len(pwd_inputs) >= 3 and not filled_old:
                        await pwd_inputs[0].fill(old_password)
                        await pwd_inputs[1].fill(chosen_pwd)
                        await pwd_inputs[2].fill(chosen_pwd)
                        filled_old = filled_new = filled_conf = True
                    elif len(pwd_inputs) == 2:
                        await pwd_inputs[0].fill(chosen_pwd)
                        await pwd_inputs[1].fill(chosen_pwd)
                        filled_new = filled_conf = True
                except Exception as e:
                    logger.warning(f"[DisneyScraper] Fallo en fallback de inputs password: {e}")

        if not (filled_new and filled_conf):
            logger.error("[DisneyScraper] No se pudieron rellenar los campos de cambio de contraseña")
            await self.take_screenshot("rotate_password_inputs_failed")
            return False

        logger.info("[DisneyScraper] Campos de password rellenados. Enviando formulario...")

        submit_btns = [
            'button:has-text("Save")',
            'button:has-text("Guardar")',
            'button:has-text("Update")',
            'button:has-text("Actualizar")',
            'button:has-text("Change Password")',
            'button:has-text("Cambiar contraseña")',
            'button:has-text("Submit")',
            'button:has-text("Enviar")',
            'button[type="submit"]',
        ]
        clicked_submit = await self._safe_click_any(submit_btns, timeout_ms=12_000)
        if not clicked_submit:
            try:
                await self.browser.page.keyboard.press("Enter")
            except Exception:
                pass

        await asyncio.sleep(2.5)
        await self.take_screenshot("rotate_password_after_submit")

        success_flags = [
            "success",
            "updated",
            "actualizada",
            "cambiada",
            "changed",
            "guardado",
            "saved",
        ]
        page_text = ""
        try:
            body = await self.browser.page.query_selector("body")
            if body:
                page_text = (await body.inner_text()).lower()
        except Exception:
            page_text = ""

        success_detected = any(f in page_text for f in success_flags)
        error_flags = ["error", "wrong", "incorrecta", "mismatch", "no coincide"]
        error_detected = any(f in page_text for f in error_flags)

        if error_detected and not success_detected:
            logger.error("[DisneyScraper] Texto de error detectado tras cambio de password")
            return False

        self.new_password = chosen_pwd
        self.password = chosen_pwd
        logger.info(
            f"[DisneyScraper] Rotación de contraseña aparentemente exitosa "
            f"(nueva longitud: {len(chosen_pwd)})"
        )
        return True

    # =========================================================================
    # 4. Actualización de PIN de perfil
    # =========================================================================

    async def update_pin(self, account_id: str, new_pin: str) -> bool:
        """Alias para update_profile_pin (impl. BaseScraper)."""
        return await self.update_profile_pin(self.profile_name, new_pin)

    async def update_profile_pin(self, profile_name: str, new_pin: str) -> bool:
        """
        Navega al selector/administración de perfiles, localiza el perfil
        indicado por nombre (búsqueda fuzzy case-insensitive) y actualiza
        su PIN numérico (4-6 dígitos).
        """
        logger.info(f"[DisneyScraper] Actualizando PIN del perfil: {profile_name}")
        pin_value = str(new_pin)
        if not pin_value.isdigit() or not (4 <= len(pin_value) <= 6):
            logger.warning(
                "[DisneyScraper] El PIN proporcionado no es numérico 4-6 dígitos; "
                "se intenta de todos modos"
            )

        if not self._logged_in:
            ok = await self.login()
            if not ok:
                raise AuthenticationException("[DisneyScraper] No autenticado para actualizar PIN")

        try:
            await self.browser.navigate(self.PROFILES_URL)
            try:
                await self.browser.page.wait_for_load_state("domcontentloaded", timeout=self.NAV_TIMEOUT_MS)
            except Exception:
                pass
            await asyncio.sleep(2.0)
        except Exception as e:
            logger.warning(f"[DisneyScraper] Navegación a /profiles fallida: {e}")

        # En Disney+ muchas veces el selector aparece al principio; si no, ir a Account → Perfiles
        try:
            admin_btns = [
                'button:has-text("Edit Profiles")',
                'button:has-text("Manage Profiles")',
                'button:has-text("Editar perfiles")',
                'button:has-text("Administrar perfiles")',
                '[data-testid*="edit-profile" i]',
                'a[href*="profile" i]',
                'button[aria-label*="edit" i]',
            ]
            await self._safe_click_any(admin_btns, timeout_ms=10_000)
            await asyncio.sleep(1.5)
        except Exception:
            pass

        # Localizar perfil por nombre
        target = None
        try:
            profiles = await self.browser.page.query_selector_all(
                ".profile-card, [data-profile-id], [data-testid*='profile' i], a[href*='/profile/']"
            )
            target_name_lc = profile_name.strip().lower()
            best_score = 0.0
            for p in profiles:
                try:
                    txt = (await p.inner_text() or "").strip()
                    if not txt:
                        continue
                    txt_lc = txt.lower()
                    score = 0.0
                    if target_name_lc == txt_lc:
                        score = 1.0
                    elif target_name_lc in txt_lc or txt_lc in target_name_lc:
                        score = 0.8
                    else:
                        # partial token match
                        tokens = target_name_lc.split()
                        matches = sum(1 for t in tokens if t and t in txt_lc)
                        score = (matches / len(tokens)) if tokens else 0.0
                    if score > 0 and score > best_score:
                        best_score = score
                        target = p
                except Exception:
                    continue
        except Exception as e:
            logger.error(f"[DisneyScraper] Error al buscar perfil: {e}")
            target = None

        if target is None:
            logger.error(
                f"[DisneyScraper] No se encontró el perfil '{profile_name}' en el listado"
            )
            await self.take_screenshot("update_pin_profile_not_found")
            return False

        logger.info(f"[DisneyScraper] Perfil localizado (score match). Abriendo edición...")
        try:
            await target.scroll_into_view_if_needed(timeout=3000)
            await target.click()
            await asyncio.sleep(1.5)
        except Exception as e:
            logger.warning(f"[DisneyScraper] Click directo en perfil falló: {e}")

        # Buscar sección de PIN / parental control
        pin_section_btns = [
            'button:has-text("Profile PIN")',
            'button:has-text("PIN de perfil")',
            'button:has-text("Parental Controls")',
            'button:has-text("Control parental")',
            'button:has-text("PIN")',
            'a:has-text("PIN")',
            '[data-testid*="pin" i]',
        ]
        await self._safe_click_any(pin_section_btns, timeout_ms=10_000)
        await asyncio.sleep(1.0)

        # Rellenar PIN nuevo (y confirmación)
        pin_selectors = [
            'input[name="pin"]',
            'input[name="profilePin"]',
            'input[name="newPin"]',
            'input[placeholder*="PIN" i]',
            'input[placeholder*="pin" i]',
            'input[type="password"][maxlength="6"]',
            'input[type="text"][maxlength="6"]',
            'input[type="number"][maxlength="6"]',
            'input[inputmode="numeric"]',
        ]

        # Crear / update toggle
        create_toggles = [
            'button[role="switch"]',
            'input[type="checkbox"]',
            'label:has-text("Use PIN")',
            'label:has-text("Usar PIN")',
        ]
        for sel in create_toggles:
            try:
                el = await self.browser.page.query_selector(sel)
                if el and await el.is_visible():
                    role = await el.get_attribute("role")
                    checked = await el.get_attribute("aria-checked")
                    if role == "switch" and checked and checked.lower() == "false":
                        await el.click()
                        await asyncio.sleep(0.6)
                    elif (await el.evaluate("el => el.tagName").lower() == "input") and not await el.is_checked():
                        await el.click()
                        await asyncio.sleep(0.6)
            except Exception:
                continue

        pin_inputs = await self.browser.page.query_selector_all('input[type="password"], input[type="text"][inputmode="numeric"], input[type="number"]')
        if len(pin_inputs) >= 2:
            # primer input: nuevo pin, segundo input: confirmar pin
            try:
                await pin_inputs[0].fill(pin_value)
                await pin_inputs[1].fill(pin_value)
            except Exception:
                pass
        else:
            filled_pin = await self._safe_fill_any(pin_selectors, pin_value, timeout_ms=10_000)
            if not filled_pin:
                logger.error("[DisneyScraper] No se pudo rellenar el campo de PIN")
                await self.take_screenshot("update_pin_input_failed")
                return False

        save_btns = [
            'button:has-text("Save")',
            'button:has-text("Guardar")',
            'button:has-text("Update")',
            'button:has-text("Actualizar")',
            'button:has-text("Create")',
            'button:has-text("Crear")',
            'button:has-text("Confirm")',
            'button:has-text("Confirmar")',
            'button[type="submit"]',
        ]
        await self._safe_click_any(save_btns, timeout_ms=10_000)
        await asyncio.sleep(2.0)

        done_btns = [
            'button:has-text("Done")',
            'button:has-text("Listo")',
            'button:has-text("Finish")',
            'button:has-text("Finalizar")',
        ]
        await self._safe_click_any(done_btns, timeout_ms=6000)

        logger.info(f"[DisneyScraper] Actualización de PIN de perfil '{profile_name}' completada")
        await self.take_screenshot(f"update_pin_{profile_name}_done")
        return True

    # =========================================================================
    # 5. Orquestación completa (entry point principal)
    # =========================================================================

    async def run_full_rotation(self) -> Dict[str, Any]:
        """
        Ejecuta la secuencia completa y retorna el diccionario de resultado
        con estado y la nueva contraseña generada (lista para Laravel API).

        Returns:
            {
                "success": bool,
                "platform": "disneyplus",
                "username": str,
                "profile_name": str,
                "profile_pin": str,
                "new_password": str or None,
                "steps": {login, revoke_devices, rotate_password, update_pin},
                "error": str (optional)
            }
        """
        result: Dict[str, Any] = {
            "success": False,
            "platform": "disneyplus",
            "username": self.username,
            "profile_name": self.profile_name,
            "profile_pin": self.profile_pin,
            "new_password": None,
            "steps": {
                "login": False,
                "revoke_devices": False,
                "rotate_password": False,
                "update_pin": False,
            },
            "error": None,
        }

        try:
            # 1. Login
            result["steps"]["login"] = await self.login()
            if not result["steps"]["login"]:
                result["error"] = "Login fallido"
                return result

            # 2. Revocar dispositivos
            try:
                result["steps"]["revoke_devices"] = await self.revoke_devices()
            except Exception as e:
                logger.warning(f"[DisneyScraper] revoke_devices reportó error (no fatal): {e}")
                result["steps"]["revoke_devices"] = False

            # 3. Rotar password maestra
            result["steps"]["rotate_password"] = await self.rotate_password()
            result["new_password"] = self.new_password
            if not result["steps"]["rotate_password"]:
                result["error"] = "Rotación de contraseña fallida"
                return result

            # 4. Actualizar PIN del perfil
            try:
                result["steps"]["update_pin"] = await self.update_profile_pin(
                    self.profile_name, self.profile_pin
                )
            except Exception as e:
                logger.warning(f"[DisneyScraper] update_profile_pin reportó error: {e}")
                result["steps"]["update_pin"] = False

            # Exito global: login + rotate_password obligatorios + new_password seteado
            result["success"] = (
                result["steps"]["login"]
                and result["steps"]["rotate_password"]
                and bool(result["new_password"])
            )
            logger.info(
                f"[DisneyScraper] run_full_rotation finalizado: "
                f"success={result['success']} steps={result['steps']}"
            )
            return result

        except Exception as e:
            logger.exception(f"[DisneyScraper] Excepción en run_full_rotation: {e}")
            result["error"] = f"{type(e).__name__}: {e}"
            return result
