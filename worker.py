#!/usr/bin/env python3
"""
Soy Grandez Engine - Background Worker
Runs the orchestrator as a scheduled background service.
"""
import asyncio
import signal
import sys
from services.orchestrator_service import OrchestratorService
from config.settings import settings
from core.logger import setup_logger

# Setup logging
logger = setup_logger("worker", log_level=settings.log_level)


class Worker:
    """Background worker for scheduled automation tasks."""
    
    def __init__(self):
        self.orchestrator = None
        self.running = False
        self._setup_signal_handlers()
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.running = False
    
    async def start(self):
        """Start the worker."""
        logger.info("=" * 60)
        logger.info("Soy Grandez Engine - Background Worker")
        logger.info("=" * 60)
        logger.info(f"Environment: {settings.app_env}")
        logger.info(f"Sync Interval: {settings.orchestrator_sync_interval_minutes} minutes")
        logger.info(f"Max Concurrent Tasks: {settings.orchestrator_max_concurrent_tasks}")
        logger.info("")
        
        self.running = True
        self.orchestrator = OrchestratorService()
        
        try:
            # Initialize orchestrator
            await self.orchestrator.initialize()
            logger.info("✅ Worker initialized successfully")
            
            # Start scheduled sync
            await self.orchestrator.run_scheduled_sync(settings.orchestrator_sync_interval_minutes)
            
        except Exception as e:
            logger.error(f"❌ Worker error: {e}")
            raise
        finally:
            await self.stop()
    
    async def stop(self):
        """Stop the worker gracefully."""
        logger.info("Stopping worker...")
        self.running = False
        
        if self.orchestrator:
            try:
                await self.orchestrator.shutdown()
                logger.info("✅ Worker stopped successfully")
            except Exception as e:
                logger.error(f"Error during shutdown: {e}")


async def main():
    """Main entry point for the worker."""
    worker = Worker()
    
    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("Worker interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Worker terminated")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)
