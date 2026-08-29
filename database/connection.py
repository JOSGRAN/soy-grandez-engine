from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import SQLAlchemyError
from contextlib import contextmanager
from config.settings import settings
import logging

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

Base = declarative_base()


class DatabaseConnection:
    def __init__(self):
        self.engine = None
        self.SessionLocal = None
        self._initialize_connection()
    
    def _initialize_connection(self):
        try:
            self.engine = create_engine(
                settings.database_url,
                pool_pre_ping=True,
                pool_recycle=3600,
                echo=settings.app_env == "development"
            )
            self.SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine
            )
            logger.info("Database connection established successfully")
        except SQLAlchemyError as e:
            logger.error(f"Failed to establish database connection: {e}")
            raise
    
    @contextmanager
    def get_session(self):
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()
    
    def test_connection(self) -> bool:
        try:
            with self.get_session() as session:
                session.execute("SELECT 1")
            logger.info("Database connection test successful")
            return True
        except SQLAlchemyError as e:
            logger.error(f"Database connection test failed: {e}")
            return False


# Global database connection instance
db_connection = DatabaseConnection()
