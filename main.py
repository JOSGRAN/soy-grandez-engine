import asyncio
import sys
import argparse
from database.connection import db_connection
from database.repository import CredentialRepository
from database.models import PlatformType, AccountStatus
from services.laravel_api_client import LaravelAPIClient
from services.orchestrator_service import OrchestratorService
from config.settings import settings
from core.logger import setup_logger, get_logger

# Setup advanced logging
logger = setup_logger("main", log_level=settings.log_level)


async def test_database_connection():
    logger.info("=" * 60)
    logger.info("TEST 1: Database Connection")
    logger.info("=" * 60)
    
    try:
        is_connected = db_connection.test_connection()
        if is_connected:
            logger.info("✅ Database connection successful")
            return True
        else:
            logger.error("❌ Database connection failed")
            return False
    except Exception as e:
        logger.error(f"❌ Database connection error: {e}")
        return False


async def test_credential_repository():
    logger.info("=" * 60)
    logger.info("TEST 2: Credential Repository")
    logger.info("=" * 60)
    
    try:
        repo = CredentialRepository()
        
        # Test getting all credentials
        credentials = repo.get_all_credentials()
        logger.info(f"✅ Retrieved {len(credentials)} credentials from database")
        
        # Test getting expired accounts
        expired_accounts = repo.get_expired_accounts()
        logger.info(f"✅ Found {len(expired_accounts)} expired accounts")
        
        if expired_accounts:
            logger.info("Sample expired account:")
            for acc in expired_accounts[:1]:
                logger.info(f"  - Account: {acc['account_name']}")
                logger.info(f"  - Platform: {acc['platform']}")
                logger.info(f"  - Username: {acc['username']}")
                logger.info(f"  - End Date: {acc['subscription_end_date']}")
        
        return True
    except Exception as e:
        logger.error(f"❌ Credential repository error: {e}")
        return False


async def test_laravel_api_authentication():
    logger.info("=" * 60)
    logger.info("TEST 3: Laravel API Authentication")
    logger.info("=" * 60)
    
    try:
        api_client = LaravelAPIClient()
        is_authenticated = await api_client.authenticate()
        
        if is_authenticated:
            logger.info("✅ Laravel API authentication successful")
            logger.info(f"API Base URL: {settings.laravel_api_url}")
            return True
        else:
            logger.error("❌ Laravel API authentication failed")
            return False
    except Exception as e:
        logger.error(f"❌ Laravel API authentication error: {e}")
        return False


async def test_laravel_api_get_accounts():
    logger.info("=" * 60)
    logger.info("TEST 4: Laravel API - Get Accounts")
    logger.info("=" * 60)
    
    try:
        api_client = LaravelAPIClient()
        
        # Authenticate first
        if not await api_client.authenticate():
            logger.error("❌ Cannot test get accounts - authentication failed")
            return False
        
        # Get all accounts
        accounts = await api_client.get_accounts()
        logger.info(f"✅ Retrieved {len(accounts)} accounts from Laravel API")
        
        if accounts:
            logger.info("Sample account:")
            for acc in accounts[:1]:
                logger.info(f"  - Account ID: {acc.get('id')}")
                logger.info(f"  - Name: {acc.get('account_name')}")
                logger.info(f"  - Status: {acc.get('status')}")
                logger.info(f"  - Platform: {acc.get('platform')}")
        
        return True
    except Exception as e:
        logger.error(f"❌ Laravel API get accounts error: {e}")
        return False


async def test_laravel_api_get_expired_subscriptions():
    logger.info("=" * 60)
    logger.info("TEST 5: Laravel API - Get Expired Subscriptions")
    logger.info("=" * 60)
    
    try:
        api_client = LaravelAPIClient()
        
        # Authenticate first
        if not await api_client.authenticate():
            logger.error("❌ Cannot test expired subscriptions - authentication failed")
            return False
        
        # Get expired subscriptions
        expired = await api_client.get_expired_subscriptions()
        logger.info(f"✅ Retrieved {len(expired)} expired subscriptions from Laravel API")
        
        if expired:
            logger.info("Sample expired subscription:")
            for sub in expired[:1]:
                logger.info(f"  - Account: {sub.get('account_name')}")
                logger.info(f"  - Plan: {sub.get('plan_name')}")
                logger.info(f"  - Renewal Date: {sub.get('renewal_date')}")
        
        return True
    except Exception as e:
        logger.error(f"❌ Laravel API get expired subscriptions error: {e}")
        return False


async def run_integration_tests():
    logger.info("🚀 Starting Soy Grandez Engine - Phase 1 Integration Tests")
    logger.info(f"Environment: {settings.app_env}")
    logger.info(f"Database: {settings.db_host}:{settings.db_port}/{settings.db_name}")
    logger.info("")
    
    results = []
    
    # Run all tests
    results.append(await test_database_connection())
    results.append(await test_credential_repository())
    results.append(await test_laravel_api_authentication())
    results.append(await test_laravel_api_get_accounts())
    results.append(await test_laravel_api_get_expired_subscriptions())
    
    # Summary
    logger.info("")
    logger.info("=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)
    total_tests = len(results)
    passed_tests = sum(results)
    logger.info(f"Total Tests: {total_tests}")
    logger.info(f"Passed: {passed_tests}")
    logger.info(f"Failed: {total_tests - passed_tests}")
    
    if all(results):
        logger.info("✅ All integration tests passed successfully!")
        return 0
    else:
        logger.error("❌ Some integration tests failed. Please check the logs above.")
        return 1


async def run_sync():
    """Run the orchestrator sync process."""
    logger.info("🚀 Starting Soy Grandez Engine - Sync Process")
    logger.info(f"Environment: {settings.app_env}")
    logger.info("")
    
    try:
        orchestrator = OrchestratorService()
        result = await orchestrator.sync_expired_accounts()
        
        logger.info("")
        logger.info("=" * 60)
        logger.info("SYNC SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Processed: {result.get('processed', 0)}")
        logger.info(f"Successful: {result.get('successful', 0)}")
        logger.info(f"Failed: {result.get('failed', 0)}")
        
        if result.get('success'):
            logger.info("✅ Sync completed successfully!")
            return 0
        else:
            logger.error(f"❌ Sync failed: {result.get('error')}")
            return 1
            
    except Exception as e:
        logger.error(f"❌ Sync process error: {e}")
        return 1
    finally:
        try:
            await orchestrator.shutdown()
        except:
            pass


async def run_single_account(account_id: str, platform: str):
    """Process a single account."""
    logger.info(f"🚀 Processing single account: {account_id} ({platform})")
    logger.info("")
    
    try:
        orchestrator = OrchestratorService()
        result = await orchestrator.process_single_account(account_id, platform)
        
        logger.info("")
        logger.info("=" * 60)
        logger.info("ACCOUNT PROCESSING SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Success: {result.get('success')}")
        logger.info(f"Message: {result.get('message')}")
        
        if result.get('success'):
            logger.info("✅ Account processed successfully!")
            return 0
        else:
            logger.error(f"❌ Account processing failed: {result.get('error')}")
            return 1
            
    except Exception as e:
        logger.error(f"❌ Account processing error: {e}")
        return 1
    finally:
        try:
            await orchestrator.shutdown()
        except:
            pass


async def run_scheduled_worker():
    """Run the orchestrator as a scheduled worker."""
    logger.info("🚀 Starting Soy Grandez Engine - Scheduled Worker")
    logger.info(f"Environment: {settings.app_env}")
    logger.info(f"Sync Interval: {settings.orchestrator_sync_interval_minutes} minutes")
    logger.info("")
    
    try:
        orchestrator = OrchestratorService()
        await orchestrator.run_scheduled_sync(settings.orchestrator_sync_interval_minutes)
    except KeyboardInterrupt:
        logger.info("Worker stopped by user")
    except Exception as e:
        logger.error(f"❌ Worker error: {e}")
    finally:
        try:
            await orchestrator.shutdown()
        except:
            pass


def main():
    """Main entry point with CLI argument parsing."""
    parser = argparse.ArgumentParser(
        description="Soy Grandez Engine - Automation Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --test              Run integration tests
  python main.py --sync              Run sync process once
  python main.py --account 123 netflix Process single account
  python main.py --worker            Run as scheduled worker
        """
    )
    
    parser.add_argument(
        '--test',
        action='store_true',
        help='Run integration tests (Phase 1)'
    )
    
    parser.add_argument(
        '--sync',
        action='store_true',
        help='Run sync process once'
    )
    
    parser.add_argument(
        '--account',
        type=str,
        metavar='ID',
        help='Process a single account by ID'
    )
    
    parser.add_argument(
        '--platform',
        type=str,
        metavar='PLATFORM',
        help='Platform for single account processing (netflix, disney, gosplit, sharesub)'
    )
    
    parser.add_argument(
        '--worker',
        action='store_true',
        help='Run as scheduled worker'
    )
    
    parser.add_argument(
        '--phase2',
        action='store_true',
        help='Run Phase 2 tests (web automation)'
    )
    
    parser.add_argument(
        '--phase3',
        action='store_true',
        help='Run Phase 3 tests (OTP Gmail)'
    )
    
    args = parser.parse_args()
    
    # If no arguments provided, show help
    if len(sys.argv) == 1:
        parser.print_help()
        return 0
    
    try:
        if args.test:
            exit_code = asyncio.run(run_integration_tests())
        elif args.sync:
            exit_code = asyncio.run(run_sync())
        elif args.account and args.platform:
            exit_code = asyncio.run(run_single_account(args.account, args.platform))
        elif args.worker:
            exit_code = asyncio.run(run_scheduled_worker())
        elif args.phase2:
            # Run Phase 2 tests
            import test_phase2
            exit_code = asyncio.run(test_phase2.run_phase2_tests())
        elif args.phase3:
            # Run Phase 3 tests
            import test_phase3
            exit_code = asyncio.run(test_phase3.run_phase3_tests())
        else:
            parser.print_help()
            exit_code = 0
        
        return exit_code
        
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        return 130
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
