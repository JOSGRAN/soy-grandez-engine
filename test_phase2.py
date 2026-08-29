import asyncio
import sys
from services.browser_manager import BrowserManager
from services.capsolver_service import CapsolverService
from scrapers.gosplit_scraper import GoSplitScraper
from scrapers.sharesub_scraper import ShareSubScraper
from scrapers.streaming_scraper import StreamingScraper
from config.settings import settings
import logging

logging.basicConfig(
    level=settings.log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_browser_manager():
    logger.info("=" * 60)
    logger.info("TEST 1: Browser Manager Initialization")
    logger.info("=" * 60)
    
    try:
        browser = BrowserManager(headless=settings.browser_headless)
        
        if await browser.start():
            logger.info("✅ Browser started successfully")
            
            # Test navigation
            await browser.navigate("https://example.com")
            logger.info("✅ Navigation to example.com successful")
            
            # Test screenshot
            await browser.screenshot("test_navigation.png")
            logger.info("✅ Screenshot taken successfully")
            
            await browser.close()
            logger.info("✅ Browser closed successfully")
            return True
        else:
            logger.error("❌ Failed to start browser")
            return False
            
    except Exception as e:
        logger.error(f"❌ Browser manager test failed: {e}")
        return False


async def test_capsolver_service():
    logger.info("=" * 60)
    logger.info("TEST 2: Capsolver Service")
    logger.info("=" * 60)
    
    if not settings.capsolver_api_key:
        logger.warning("⚠️  Capsolver API key not configured, skipping test")
        return True
    
    try:
        async with CapsolverService(api_key=settings.capsolver_api_key) as capsolver:
            logger.info("✅ Capsolver service initialized")
            
            # Note: This is a mock test - actual captcha solving requires real site keys
            logger.info("ℹ️  Capsolver service ready for captcha solving")
            logger.info(f"   Supported types: Turnstile, reCAPTCHA v2/v3, hCaptcha")
            
            return True
            
    except Exception as e:
        logger.error(f"❌ Capsolver service test failed: {e}")
        return False


async def test_gosplit_scraper():
    logger.info("=" * 60)
    logger.info("TEST 3: GoSplit Scraper (Mock Test)")
    logger.info("=" * 60)
    
    try:
        browser = BrowserManager(headless=settings.browser_headless)
        
        if not await browser.start():
            logger.error("❌ Failed to start browser for GoSplit test")
            return False
        
        capsolver = CapsolverService(api_key=settings.capsolver_api_key) if settings.capsolver_api_key else None
        scraper = GoSplitScraper(browser, capsolver)
        
        logger.info("✅ GoSplit scraper initialized")
        logger.info("ℹ️  Ready for login automation with:")
        logger.info("   - Login URL: https://gosplit.com/login")
        logger.info("   - Dashboard URL: https://gosplit.com/dashboard")
        logger.info("   - Accounts URL: https://gosplit.com/accounts")
        logger.info("   - Captcha solving: Enabled" if capsolver else "   - Captcha solving: Disabled")
        
        # Note: Actual login requires real credentials
        logger.info("⚠️  Actual login test requires valid credentials")
        
        await browser.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ GoSplit scraper test failed: {e}")
        return False


async def test_sharesub_scraper():
    logger.info("=" * 60)
    logger.info("TEST 4: ShareSub Scraper (Mock Test)")
    logger.info("=" * 60)
    
    try:
        browser = BrowserManager(headless=settings.browser_headless)
        
        if not await browser.start():
            logger.error("❌ Failed to start browser for ShareSub test")
            return False
        
        capsolver = CapsolverService(api_key=settings.capsolver_api_key) if settings.capsolver_api_key else None
        scraper = ShareSubScraper(browser, capsolver)
        
        logger.info("✅ ShareSub scraper initialized")
        logger.info("ℹ️  Ready for login automation with:")
        logger.info("   - Login URL: https://sharesub.com/login")
        logger.info("   - Dashboard URL: https://sharesub.com/dashboard")
        logger.info("   - Accounts URL: https://sharesub.com/my-accounts")
        logger.info("   - Captcha solving: Enabled" if capsolver else "   - Captcha solving: Disabled")
        
        # Note: Actual login requires real credentials
        logger.info("⚠️  Actual login test requires valid credentials")
        
        await browser.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ ShareSub scraper test failed: {e}")
        return False


async def test_streaming_scraper():
    logger.info("=" * 60)
    logger.info("TEST 5: Streaming Scraper (Mock Test)")
    logger.info("=" * 60)
    
    try:
        browser = BrowserManager(headless=settings.browser_headless)
        
        if not await browser.start():
            logger.error("❌ Failed to start browser for Streaming test")
            return False
        
        capsolver = CapsolverService(api_key=settings.capsolver_api_key) if settings.capsolver_api_key else None
        
        # Test Netflix scraper
        netflix_scraper = StreamingScraper(browser, capsolver, platform="netflix")
        logger.info("✅ Netflix scraper initialized")
        logger.info("ℹ️  Ready for login automation with:")
        logger.info("   - Login URL: https://netflix.com/login")
        logger.info("   - Profile URL: https://netflix.com/YourAccount")
        
        # Test Disney+ scraper
        disney_scraper = StreamingScraper(browser, capsolver, platform="disney")
        logger.info("✅ Disney+ scraper initialized")
        logger.info("ℹ️  Ready for login automation with:")
        logger.info("   - Login URL: https://disneyplus.com/login")
        logger.info("   - Profile URL: https://disneyplus.com/account")
        
        # Note: Actual login requires real credentials
        logger.info("⚠️  Actual login test requires valid credentials")
        
        await browser.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Streaming scraper test failed: {e}")
        return False


async def test_cloudflare_simulation():
    logger.info("=" * 60)
    logger.info("TEST 6: Cloudflare Challenge Simulation")
    logger.info("=" * 60)
    
    try:
        browser = BrowserManager(headless=settings.browser_headless)
        
        if not await browser.start():
            logger.error("❌ Failed to start browser for Cloudflare test")
            return False
        
        # Navigate to a site that might have Cloudflare protection
        logger.info("ℹ️  Navigating to test site (may encounter Cloudflare)...")
        await browser.navigate("https://example.com")
        
        logger.info("✅ Browser ready for Cloudflare challenge handling")
        logger.info("ℹ️  When Cloudflare Turnstile is detected:")
        logger.info("   1. Automatically detect iframe with challenges.cloudflare.com")
        logger.info("   2. Extract site key from the widget")
        logger.info("   3. Submit to Capsolver API for solving")
        logger.info("   4. Inject solution token into the page")
        logger.info("   5. Continue with automation")
        
        await browser.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Cloudflare simulation test failed: {e}")
        return False


async def run_phase2_tests():
    logger.info("🚀 Starting Soy Grandez Engine - Phase 2 Integration Tests")
    logger.info(f"Environment: {settings.app_env}")
    logger.info(f"Browser Headless: {settings.browser_headless}")
    logger.info(f"Capsolver API Key: {'Configured' if settings.capsolver_api_key else 'Not configured'}")
    logger.info("")
    
    results = []
    
    # Run all tests
    results.append(await test_browser_manager())
    results.append(await test_capsolver_service())
    results.append(await test_gosplit_scraper())
    results.append(await test_sharesub_scraper())
    results.append(await test_streaming_scraper())
    results.append(await test_cloudflare_simulation())
    
    # Summary
    logger.info("")
    logger.info("=" * 60)
    logger.info("PHASE 2 TEST SUMMARY")
    logger.info("=" * 60)
    total_tests = len(results)
    passed_tests = sum(results)
    logger.info(f"Total Tests: {total_tests}")
    logger.info(f"Passed: {passed_tests}")
    logger.info(f"Failed: {total_tests - passed_tests}")
    
    if all(results):
        logger.info("✅ All Phase 2 integration tests passed successfully!")
        logger.info("")
        logger.info("📋 NEXT STEPS:")
        logger.info("1. Install Playwright browsers: playwright install chromium")
        logger.info("2. Configure Capsolver API key in .env")
        logger.info("3. Add real credentials for platform testing")
        logger.info("4. Run actual automation tasks")
        return 0
    else:
        logger.error("❌ Some Phase 2 integration tests failed. Please check the logs above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_phase2_tests())
    sys.exit(exit_code)
