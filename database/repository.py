from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import List, Optional, Dict, Any
from datetime import datetime
from database.models import Credential, Account, Subscription, PlatformType, AccountStatus
from database.connection import db_connection
import logging

logger = logging.getLogger(__name__)


class CredentialRepository:
    def __init__(self):
        self.db = db_connection
    
    def get_all_credentials(self, platform: Optional[PlatformType] = None) -> List[Credential]:
        with self.db.get_session() as session:
            query = session.query(Credential)
            if platform:
                query = query.filter(Credential.platform == platform)
            return query.filter(Credential.is_active == True).all()
    
    def get_credential_by_id(self, credential_id: int) -> Optional[Credential]:
        with self.db.get_session() as session:
            return session.query(Credential).filter(Credential.id == credential_id).first()
    
    def get_credential_by_username(self, username: str, platform: PlatformType) -> Optional[Credential]:
        with self.db.get_session() as session:
            return session.query(Credential).filter(
                and_(
                    Credential.username == username,
                    Credential.platform == platform,
                    Credential.is_active == True
                )
            ).first()
    
    def get_expired_accounts(self) -> List[Dict[str, Any]]:
        with self.db.get_session() as session:
            current_date = datetime.utcnow()
            expired_accounts = session.query(
                Account.id,
                Account.platform_account_id,
                Account.account_name,
                Account.subscription_end_date,
                Credential.platform,
                Credential.username
            ).join(
                Credential, Account.credential_id == Credential.id
            ).filter(
                and_(
                    Account.subscription_end_date < current_date,
                    Account.status == AccountStatus.ACTIVE
                )
            ).all()
            
            return [
                {
                    'id': acc.id,
                    'platform_account_id': acc.platform_account_id,
                    'account_name': acc.account_name,
                    'subscription_end_date': acc.subscription_end_date,
                    'platform': acc.platform,
                    'username': acc.username
                }
                for acc in expired_accounts
            ]
    
    def get_account_subscriptions(self, account_id: int) -> List[Subscription]:
        with self.db.get_session() as session:
            return session.query(Subscription).filter(
                Subscription.account_id == account_id
            ).all()
    
    def update_account_status(self, account_id: int, status: AccountStatus) -> bool:
        try:
            with self.db.get_session() as session:
                account = session.query(Account).filter(Account.id == account_id).first()
                if account:
                    account.status = status
                    account.last_sync_at = datetime.utcnow()
                    return True
                return False
        except Exception as e:
            logger.error(f"Error updating account status: {e}")
            return False
    
    def create_credential(self, credential_data: Dict[str, Any]) -> Optional[Credential]:
        try:
            with self.db.get_session() as session:
                new_credential = Credential(**credential_data)
                session.add(new_credential)
                session.flush()
                session.refresh(new_credential)
                return new_credential
        except Exception as e:
            logger.error(f"Error creating credential: {e}")
            return None
