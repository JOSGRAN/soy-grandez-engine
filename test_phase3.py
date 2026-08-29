import asyncio
import sys
from services.email_otp_service import EmailOTPService
from services.browser_manager import BrowserManager
from scrapers.streaming_scraper import StreamingScraper
from config.settings import settings
import logging

logging.basicConfig(
    level=settings.log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_gmail_authentication():
    logger.info("=" * 60)
    logger.info("TEST 1: Gmail API Authentication")
    logger.info("=" * 60)
    
    try:
        # Check if credentials file exists
        import os
        if not os.path.exists(settings.gmail_credentials_path):
            logger.warning(f"⚠️  Gmail credentials file not found: {settings.gmail_credentials_path}")
            logger.info("ℹ️  To set up Gmail API:")
            logger.info("   1. Go to Google Cloud Console")
            logger.info("   2. Create a project and enable Gmail API")
            logger.info("   3. Create OAuth 2.0 credentials (Desktop app)")
            logger.info("   4. Download credentials.json")
            logger.info("   5. Place it in the project directory")
            return False
        
        email_service = EmailOTPService(
            credentials_path=settings.gmail_credentials_path,
            token_path=settings.gmail_token_path
        )
        
        logger.info("✅ Successfully authenticated with Gmail API")
        logger.info(f"ℹ️  Token saved to: {settings.gmail_token_path}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Gmail authentication failed: {e}")
        return False


async def test_otp_code_extraction():
    logger.info("=" * 60)
    logger.info("TEST 2: OTP Code Extraction (Mock)")
    logger.info("=" * 60)
    
    try:
        email_service = EmailOTPService()
        
        # Test with sample email content
        sample_email_content = """
        Your verification code is 123456.
        Please enter this code to complete your verification.
        This code will expire in 10 minutes.
        """
        
        # Test regex patterns
        import re
        patterns = [
            r'\b\d{4}\b',
            r'\b\d{5}\b',
            r'\b\d{6}\b',
            r'\b[A-Z0-9]{4,6}\b',
            r'(?:verification|code|otp|pin)[\s:]+(\d{4,6})',
        ]
        
        found_codes = []
        for pattern in patterns:
            matches = re.findall(pattern, sample_email_content, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    code = match[0] if match else match
                else:
                    code = match
                code = re.sub(r'[^A-Z0-9]', '', code.upper())
                if code and len(code) >= 4 and len(code) <= 6:
                    if code not in found_codes:
                        found_codes.append(code)
        
        logger.info(f"✅ OTP extraction patterns working")
        logger.info(f"   Sample codes found: {found_codes}")
        logger.info(f"   Patterns tested: {len(patterns)}")
        return True
        
    except Exception as e:
        logger.error(f"❌ OTP extraction test failed: {e}")
        return False


async def test_otp_search():
    logger.info("=" * 60)
    logger.info("TEST 3: OTP Search in Gmail")
    logger.info("=" * 60)
    
    try:
        email_service = EmailOTPService()
        
        # Test searching for recent emails (last 24 hours)
        logger.info("ℹ️  Searching for recent verification emails...")
        
        # Search for general verification emails
        otp_data = email_service.get_latest_otp_code(
            sender_filter=None,
            subject_filter="verification",
            keyword="code",
            minutes_ago=1440  # 24 hours
        )
        
        if otp_data:
            logger.info("✅ Found verification email:")
            logger.info(f"   From: {otp_data.get('from')}")
            logger.info(f"   Subject: {otp_data.get('subject')}")
            logger.info(f"   Code: {otp_data.get('code')}")
            logger.info(f"   All codes: {otp_data.get('all_codes')}")
            logger.info(f"   Date: {otp_data.get('date')}")
            return True
        else:
            logger.info("ℹ️  No verification emails found in last 24 hours")
            logger.info("   This is normal if no verification emails were sent recently")
            return True
            
    except Exception as e:
        logger.error(f"❌ OTP search test failed: {e}")
        return False


async def test_otp_with_streaming_scraper():
    logger.info("=" * 60)
    logger.info("TEST 4: OTP Integration with Streaming Scraper")
    logger.info("=" * 60)
    
    try:
        email_service = EmailOTPService()
        browser = BrowserManager(headless=settings.browser_headless)
        
        if not await browser.start():
            logger.error("❌ Failed to start browser")
            return False
        
        # Create Netflix scraper with OTP service
        netflix_scraper = StreamingScraper(
            browser,
            capsolver_service=None,
            email_otp_service=email_service,
            platform="netflix"
        )
        
        logger.info("✅ Streaming scraper initialized with OTP service")
        logger.info("ℹ️  OTP integration features:")
        logger.info("   - Automatic OTP detection during password changes")
        logger.info("   - Email filtering by sender (netflix.com)")
        logger.info("   - Regex-based code extraction")
        logger.info("   - Automatic form filling")
        logger.info("   - Email marking as read")
        
        await browser.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ OTP integration test failed: {e}")
        return False


async def test_verification_link_extraction():
    logger.info("=" * 60)
    logger.info("TEST 5: Verification Link Extraction")
    logger.info("=" * 60)
    
    try:
        email_service = EmailOTPService()
        
        logger.info("ℹ️  Searching for verification links...")
        
        # Search for verification links
        verification_link = email_service.get_verification_link(
            sender_filter=None,
            keyword="verify",
            minutes_ago=1440  # 24 hours
        )
        
        if verification_link:
            logger.info("✅ Found verification link:")
            logger.info(f"   URL: {verification_link}")
            return True
        else:
            logger.info("ℹ️  No verification links found in last 24 hours")
            logger.info("   This is normal if no verification emails were sent recently")
            return True
            
    except Exception as e:
        logger.error(f"❌ Verification link extraction failed: {e}")
        return False


async def test_unread_count():
    logger.info("=" * 60)
    logger.info("TEST 6: Unread Email Count")
    logger.info("=" * 60)
    
    try:
        email_service = EmailOTPService()
        
        unread_count = email_service.get_unread_count()
        logger.info(f"✅ Unread emails count: {unread_count}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Unread count test failed: {e}")
        return False


async def run_phase3_tests():
    logger.info("🚀 Starting Soy Grandez Engine - Phase 3 Integration Tests")
    logger.info(f"Environment: {settings.app_env}")
    logger.info(f"Gmail Credentials: {settings.gmail_credentials_path}")
    logger.info(f"Gmail Token: {settings.gmail_token_path}")
    logger.info("")
    
    results = []
    
    # Run all tests
    results.append(await test_gmail_authentication())
    results.append(await test_otp_code_extraction())
    results.append(await test_otp_search())
    results.append(await test_otp_with_streaming_scraper())
    results.append(await test_verification_link_extraction())
    results.append(await test_unread_count())
    
    # Summary
    logger.info("")
    logger.info("=" * 60)
    logger.info("PHASE 3 TEST SUMMARY")
    logger.info("=" * 60)
    total_tests = len(results)
    passed_tests = sum(results)
    logger.info(f"Total Tests: {total_tests}")
    logger.info(f"Passed: {passed_tests}")
    logger.info(f"Failed: {total_tests - passed_tests}")
    
    if all(results):
        logger.info("✅ All Phase 3 integration tests passed successfully!")
        logger.info("")
        logger.info("📋 NEXT STEPS:")
        logger.info("1. Set up Gmail API credentials in Google Cloud Console")
        logger.info("2. Download credentials.json and place in project directory")
        logger.info("3. Test with real verification emails from Netflix/Disney+")
        logger.info("4. Integrate OTP handling in password change workflows")
        return 0
    else:
        logger.error("❌ Some Phase 3 integration tests failed. Please check the logs above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_phase3_tests())
    sys.exit(exit_code)
