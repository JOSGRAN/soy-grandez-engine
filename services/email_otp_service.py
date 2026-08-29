import re
import base64
import email
from email.message import EmailMessage
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import logging
import os
import pickle
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from config.settings import settings

logger = logging.getLogger(__name__)

# Gmail API scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']


class EmailOTPService:
    def __init__(self, credentials_path: Optional[str] = None, token_path: Optional[str] = None):
        self.credentials_path = credentials_path or os.getenv('GMAIL_CREDENTIALS_PATH', 'credentials.json')
        self.token_path = token_path or os.getenv('GMAIL_TOKEN_PATH', 'token.pickle')
        self.service = None
        self._authenticate()
    
    def _authenticate(self):
        """Authenticate with Gmail API using OAuth2"""
        try:
            creds = None
            
            # Load existing token if available
            if os.path.exists(self.token_path):
                with open(self.token_path, 'rb') as token:
                    creds = pickle.load(token)
            
            # If there are no (valid) credentials available, let the user log in
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    if not os.path.exists(self.credentials_path):
                        logger.error(f"Gmail credentials file not found at {self.credentials_path}")
                        logger.error("Please download credentials.json from Google Cloud Console")
                        raise FileNotFoundError(f"Credentials file not found: {self.credentials_path}")
                    
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_path, SCOPES
                    )
                    creds = flow.run_local_server(port=0)
                
                # Save the credentials for the next run
                with open(self.token_path, 'wb') as token:
                    pickle.dump(creds, token)
            
            # Build the Gmail service
            self.service = build('gmail', 'v1', credentials=creds)
            logger.info("Successfully authenticated with Gmail API")
            
        except Exception as e:
            logger.error(f"Error authenticating with Gmail API: {e}")
            raise
    
    def _decode_message(self, message: Dict[str, Any]) -> EmailMessage:
        """Decode Gmail message payload"""
        msg_str = base64.urlsafe_b64decode(message['payload']['body']['data']).decode()
        return email.message_from_string(msg_str)
    
    def _extract_text_from_message(self, message: Dict[str, Any]) -> str:
        """Extract text content from Gmail message"""
        try:
            payload = message['payload']
            
            # Check if message body is directly in payload
            if 'body' in payload and 'data' in payload['body']:
                return base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')
            
            # Check for multipart message
            if 'parts' in payload:
                for part in payload['parts']:
                    if 'body' in part and 'data' in part['body']:
                        mime_type = part.get('mimeType', '')
                        if mime_type == 'text/plain' or mime_type == 'text/html':
                            data = part['body']['data']
                            return base64.urlsafe_b64decode(data).decode('utf-8')
            
            return ""
            
        except Exception as e:
            logger.error(f"Error extracting text from message: {e}")
            return ""
    
    def _extract_otp_patterns(self, text: str) -> List[str]:
        """Extract OTP codes using multiple regex patterns"""
        otp_patterns = [
            # 4-6 digit codes
            r'\b\d{4}\b',
            r'\b\d{5}\b',
            r'\b\d{6}\b',
            # Alphanumeric codes (common in Netflix/Disney+)
            r'\b[A-Z0-9]{4,6}\b',
            # Codes with specific formatting
            r'\b\d{3}[-\s]?\d{3}\b',
            r'\b\d{2}[-\s]?\d{2}[-\s]?\d{2}\b',
            # Verification code patterns
            r'(?:verification|code|otp|pin)[\s:]+(\d{4,6})',
            r'(?:código|verificación)[\s:]+(\d{4,6})',
        ]
        
        found_codes = []
        for pattern in otp_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                # Extract the actual code if pattern has groups
                if isinstance(match, tuple):
                    code = match[0] if match else match
                else:
                    code = match
                
                # Clean the code
                code = re.sub(r'[^A-Z0-9]', '', code.upper())
                
                # Only add if it's a valid code format
                if code and len(code) >= 4 and len(code) <= 6:
                    if code not in found_codes:
                        found_codes.append(code)
        
        return found_codes
    
    def get_latest_otp_code(
        self,
        sender_filter: Optional[str] = None,
        subject_filter: Optional[str] = None,
        keyword: Optional[str] = None,
        minutes_ago: int = 5
    ) -> Optional[Dict[str, Any]]:
        """
        Get the latest OTP code from recent emails
        
        Args:
            sender_filter: Filter by sender email (e.g., 'netflix.com', 'disneyplus.com')
            subject_filter: Filter by subject keywords
            keyword: Additional keyword to search in email body
            minutes_ago: Only look at emails from the last N minutes
        
        Returns:
            Dictionary with 'code', 'from', 'subject', 'date' or None if not found
        """
        try:
            # Build query
            query_parts = []
            
            if sender_filter:
                query_parts.append(f"from:{sender_filter}")
            
            if subject_filter:
                query_parts.append(f"subject:{subject_filter}")
            
            if keyword:
                query_parts.append(keyword)
            
            # Add time filter
            time_filter = f"newer_than:{minutes_ago}m"
            query_parts.append(time_filter)
            
            query = " ".join(query_parts) if query_parts else time_filter
            
            logger.info(f"Searching for emails with query: {query}")
            
            # Search messages
            results = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=10
            ).execute()
            
            messages = results.get('messages', [])
            
            if not messages:
                logger.info(f"No emails found matching criteria")
                return None
            
            # Process messages to find OTP
            for msg in messages:
                try:
                    # Get full message
                    msg_data = self.service.users().messages().get(
                        userId='me',
                        id=msg['id'],
                        format='full'
                    ).execute()
                    
                    # Extract headers
                    headers = {h['name']: h['value'] for h in msg_data['payload']['headers']}
                    sender = headers.get('From', '')
                    subject = headers.get('Subject', '')
                    date_str = headers.get('Date', '')
                    
                    # Extract body text
                    body_text = self._extract_text_from_message(msg_data)
                    
                    # Search for OTP codes
                    otp_codes = self._extract_otp_patterns(body_text)
                    
                    if otp_codes:
                        # Return the first/most likely code
                        logger.info(f"Found OTP code in email from {sender}")
                        return {
                            'code': otp_codes[0],
                            'all_codes': otp_codes,
                            'from': sender,
                            'subject': subject,
                            'date': date_str,
                            'message_id': msg['id'],
                            'body_preview': body_text[:200] + "..." if len(body_text) > 200 else body_text
                        }
                    
                except Exception as e:
                    logger.error(f"Error processing message {msg['id']}: {e}")
                    continue
            
            logger.info("No OTP codes found in matching emails")
            return None
            
        except HttpError as e:
            logger.error(f"Gmail API error: {e}")
            return None
        except Exception as e:
            logger.error(f"Error getting latest OTP code: {e}")
            return None
    
    def get_verification_link(
        self,
        sender_filter: Optional[str] = None,
        keyword: str = "verify",
        minutes_ago: int = 5
    ) -> Optional[str]:
        """
        Get verification link from recent emails
        
        Args:
            sender_filter: Filter by sender email
            keyword: Keyword to search for (default: "verify")
            minutes_ago: Only look at emails from the last N minutes
        
        Returns:
            Verification URL or None if not found
        """
        try:
            query_parts = []
            
            if sender_filter:
                query_parts.append(f"from:{sender_filter}")
            
            query_parts.append(keyword)
            query_parts.append(f"newer_than:{minutes_ago}m")
            
            query = " ".join(query_parts)
            
            logger.info(f"Searching for verification links with query: {query}")
            
            results = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=5
            ).execute()
            
            messages = results.get('messages', [])
            
            if not messages:
                return None
            
            for msg in messages:
                try:
                    msg_data = self.service.users().messages().get(
                        userId='me',
                        id=msg['id'],
                        format='full'
                    ).execute()
                    
                    body_text = self._extract_text_from_message(msg_data)
                    
                    # Extract URLs using regex
                    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
                    urls = re.findall(url_pattern, body_text)
                    
                    # Filter for verification-like URLs
                    verification_keywords = ['verify', 'confirm', 'auth', 'token', 'access']
                    for url in urls:
                        if any(keyword in url.lower() for keyword in verification_keywords):
                            logger.info(f"Found verification link: {url}")
                            return url
                    
                except Exception as e:
                    logger.error(f"Error processing message {msg['id']}: {e}")
                    continue
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting verification link: {e}")
            return None
    
    def mark_as_read(self, message_id: str) -> bool:
        """Mark a message as read"""
        try:
            self.service.users().messages().modify(
                userId='me',
                id=message_id,
                body={'removeLabelIds': ['UNREAD']}
            ).execute()
            logger.info(f"Marked message {message_id} as read")
            return True
        except Exception as e:
            logger.error(f"Error marking message as read: {e}")
            return False
    
    def get_unread_count(self) -> int:
        """Get count of unread emails"""
        try:
            results = self.service.users().messages().list(
                userId='me',
                q='is:unread'
            ).execute()
            return results.get('resultSizeEstimate', 0)
        except Exception as e:
            logger.error(f"Error getting unread count: {e}")
            return 0
