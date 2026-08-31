import re
import base64
import email
import imaplib
import ssl
from email.message import EmailMessage
from email.header import decode_header
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import logging
import os
import pickle
import time
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
        
    async def get_latest_otp(self, sender_filter: Optional[str] = None, subject_filter: Optional[str] = None, keyword: Optional[str] = None, minutes_ago: int = 5, **kwargs):
        """Alias de compatibilidad para get_latest_otp_code con tolerancia a argumentos extra"""
        return self.get_latest_otp_code(
            sender_filter=sender_filter,
            subject_filter=subject_filter,
            keyword=keyword,
            minutes_ago=minutes_ago
        )

    def _authenticate(self):
        """Authenticate with Gmail API using OAuth2"""
        try:
            creds = None
            
            # Load existing token if available
            if os.path.exists(self.token_path) and os.path.getsize(self.token_path) > 0:
                with open(self.token_path, 'rb') as token:
                    creds = pickle.load(token)
            
            # If there are no (valid) credentials available, check if we can mock in dev
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    if not os.path.exists(self.credentials_path) or (os.path.exists(self.token_path) and os.path.getsize(self.token_path) == 0):
                        logger.warning("⚠️ Running in mock mode for Gmail API (development/testing)")
                        self.service = None
                        return
                    
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
            logger.warning(f"⚠️ Gmail API authentication skipped/mocked due to: {e}")
            self.service = None
    
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
        """Get the latest OTP code from recent emails"""
        if not self.service:
            logger.info("Gmail service is mocked. Returning dummy OTP data for testing.")
            return {
                'code': '123456',
                'all_codes': ['123456'],
                'from': sender_filter or 'test@streaming.com',
                'subject': subject_filter or 'Your verification code',
                'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'message_id': 'mock_id_123',
                'body_preview': 'Your verification code is 123456'
            }
        try:
            query_parts = []
            
            if sender_filter:
                query_parts.append(f"from:{sender_filter}")
            
            if subject_filter:
                query_parts.append(f"subject:{subject_filter}")
            
            if keyword:
                query_parts.append(keyword)
            
            time_filter = f"newer_than:{minutes_ago}m"
            query_parts.append(time_filter)
            
            query = " ".join(query_parts) if query_parts else time_filter
            
            logger.info(f"Searching for emails with query: {query}")
            
            results = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=10
            ).execute()
            
            messages = results.get('messages', [])
            
            if not messages:
                logger.info(f"No emails found matching criteria")
                return None
            
            for msg in messages:
                try:
                    msg_data = self.service.users().messages().get(
                        userId='me',
                        id=msg['id'],
                        format='full'
                    ).execute()
                    
                    headers = {h['name']: h['value'] for h in msg_data['payload']['headers']}
                    sender = headers.get('From', '')
                    subject = headers.get('Subject', '')
                    date_str = headers.get('Date', '')
                    
                    body_text = self._extract_text_from_message(msg_data)
                    otp_codes = self._extract_otp_patterns(body_text)
                    
                    if otp_codes:
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
        """Get verification link from recent emails"""
        if not self.service:
            logger.info("Gmail service is mocked. Returning dummy verification link.")
            return "https://example.com/verify?token=mock_token_123"
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
                    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
                    urls = re.findall(url_pattern, body_text)
                    
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
        if not self.service:
            logger.info("Gmail service is mocked. Skipping mark_as_read.")
            return True
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
        if not self.service:
            logger.info("Gmail service is mocked. Returning dummy unread count.")
            return 0
        try:
            results = self.service.users().messages().list(
                userId='me',
                q='is:unread'
            ).execute()
            return results.get('resultSizeEstimate', 0)
        except Exception as e:
            logger.error(f"Error getting unread count: {e}")
            return 0

    @staticmethod
    def _decode_imap_header(raw_header: str) -> str:
        """Decode MIME encoded-word headers into a readable UTF-8 string."""
        try:
            parts = decode_header(raw_header)
            decoded = []
            for text, charset in parts:
                if isinstance(text, bytes):
                    try:
                        decoded.append(text.decode(charset or 'utf-8', errors='replace'))
                    except Exception:
                        decoded.append(text.decode('utf-8', errors='replace'))
                else:
                    decoded.append(str(text))
            return " ".join(decoded)
        except Exception:
            return str(raw_header)

    @staticmethod
    def _extract_body_from_imap_message(msg) -> str:
        """Extract plain text + HTML body from an IMAP email.message.Message."""
        body_parts = []
        try:
            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get("Content-Disposition", ""))
                    if "attachment" in content_disposition:
                        continue
                    if content_type in ("text/plain", "text/html"):
                        payload = part.get_payload(decode=True)
                        if payload:
                            charset = part.get_content_charset() or "utf-8"
                            try:
                                body_parts.append(payload.decode(charset, errors="replace"))
                            except Exception:
                                body_parts.append(payload.decode("utf-8", errors="replace"))
            else:
                payload = msg.get_payload(decode=True)
                if payload:
                    charset = msg.get_content_charset() or "utf-8"
                    try:
                        body_parts.append(payload.decode(charset, errors="replace"))
                    except Exception:
                        body_parts.append(payload.decode("utf-8", errors="replace"))
        except Exception as e:
            logger.error(f"Error extracting body from IMAP message: {e}")
        return "\n".join(body_parts)

    def get_disney_otp_via_imap(
        self,
        email_address: str,
        app_password: str,
        timeout_seconds: int = 30,
        poll_interval: int = 3,
        minutes_ago: int = 5
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch the most recent Disney+ 6-digit OTP code via Gmail IMAP using an
        App Password (16 chars).

        Args:
            email_address: Gmail address (e.g., usuario@gmail.com)
            app_password: Google 16-character App Password (no spaces, or w/ spaces)
            timeout_seconds: Max seconds to poll for a new email
            poll_interval: Seconds between IMAP polls
            minutes_ago: Lookback window for recent messages

        Returns:
            Dict with keys: code, from, subject, date, body_preview, message_id
            None if no OTP was found within the timeout.
        """
        if not email_address or not app_password:
            logger.error("get_disney_otp_via_imap called without email_address or app_password")
            return None

        clean_password = app_password.replace(" ", "")
        cutoff_date = (datetime.now() - timedelta(minutes=minutes_ago))
        start_ts = time.time()
        last_seen_ids: set = set()

        disney_senders = [
            "disneyplus.com",
            "disney-plus.com",
            "thewaltdisneycompany.com",
            "disney.com",
            "no-reply@disneyplus.com",
            "noreply@disneyplus.com",
        ]
        disney_subjects = [
            "verification",
            "código",
            "codigo",
            "one-time",
            "otp",
            "security",
            "seguridad",
            "iniciar sesión",
            "sign-in",
            "sign in",
            "access",
            "acceso",
        ]

        logger.info(
            f"[IMAP] Polling Disney+ OTP for {email_address} "
            f"(timeout={timeout_seconds}s, lookback={minutes_ago}m)"
        )

        while (time.time() - start_ts) < timeout_seconds:
            mail = None
            try:
                ctx = ssl.create_default_context()
                mail = imaplib.IMAP4_SSL("imap.gmail.com", 993, ssl_context=ctx)
                mail.login(email_address, clean_password)
                mail.select("INBOX", readonly=True)

                status, _ = mail.search(None, f'(SINCE "{cutoff_date.strftime("%d-%b-%Y")}")')
                if status != "OK":
                    logger.warning("[IMAP] SEARCH command returned non-OK status")
                    mail.close()
                    mail.logout()
                    time.sleep(poll_interval)
                    continue

                msg_ids = _[0].split() if _ and _[0] else []
                msg_ids = list(reversed(msg_ids))

                if not msg_ids:
                    logger.debug("[IMAP] No messages found in lookback window")
                    mail.close()
                    mail.logout()
                    time.sleep(poll_interval)
                    continue

                for msg_id in msg_ids:
                    if msg_id in last_seen_ids:
                        continue
                    last_seen_ids.add(msg_id)

                    status, msg_data = mail.fetch(msg_id, "(RFC822)")
                    if status != "OK" or not msg_data or not msg_data[0]:
                        continue

                    raw_email = msg_data[0][1]
                    msg = email.message_from_bytes(raw_email)

                    raw_from = msg.get("From", "")
                    raw_subject = msg.get("Subject", "")
                    raw_date = msg.get("Date", "")
                    sender = self._decode_imap_header(raw_from)
                    subject = self._decode_imap_header(raw_subject)

                    sender_lc = sender.lower()
                    subject_lc = subject.lower()
                    matches_sender = any(s in sender_lc for s in disney_senders)
                    matches_subject = any(k in subject_lc for k in disney_subjects)

                    if not (matches_sender or matches_subject):
                        continue

                    body_text = self._extract_body_from_imap_message(msg)
                    combined_search_text = f"{subject} {body_text}"
                    otp_codes = self._extract_otp_patterns(combined_search_text)

                    six_digit_codes = [c for c in otp_codes if c.isdigit() and len(c) == 6]
                    if not six_digit_codes:
                        six_digit_codes = [c for c in otp_codes if len(c) == 6]

                    if six_digit_codes:
                        chosen = six_digit_codes[0]
                        logger.info(
                            f"[IMAP] Disney+ OTP found: {chosen} "
                            f"(from={sender[:80]}, subject={subject[:80]})"
                        )
                        try:
                            mail.close()
                            mail.logout()
                        except Exception:
                            pass
                        return {
                            "code": chosen,
                            "all_codes": otp_codes,
                            "from": sender,
                            "subject": subject,
                            "date": raw_date,
                            "message_id": msg.get("Message-ID", msg_id.decode() if isinstance(msg_id, bytes) else str(msg_id)),
                            "body_preview": (body_text[:200] + "...") if len(body_text) > 200 else body_text,
                            "via": "IMAP",
                        }

                try:
                    mail.close()
                    mail.logout()
                except Exception:
                    pass

            except imaplib.IMAP4.error as e:
                logger.error(f"[IMAP] Authentication/IMAP error for {email_address}: {e}")
                return None
            except Exception as e:
                logger.error(f"[IMAP] Unexpected error while polling OTP: {e}")
                try:
                    if mail is not None:
                        try:
                            mail.close()
                        except Exception:
                            pass
                        try:
                            mail.logout()
                        except Exception:
                            pass
                except Exception:
                    pass
            finally:
                mail = None

            time.sleep(poll_interval)

        logger.warning(f"[IMAP] Disney+ OTP not found within {timeout_seconds}s for {email_address}")
        return None

        
