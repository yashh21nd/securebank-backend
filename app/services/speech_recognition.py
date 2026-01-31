"""
Speech Recognition Service for Voice-based Payments
Supports voice commands for payments like GPay/PhonePe
"""
import speech_recognition as sr
import re
from datetime import datetime
import json


class VoicePaymentParser:
    """
    Parse voice commands for payment operations
    Supports commands like:
    - "Send 500 rupees to John"
    - "Pay 1000 to mom"
    - "Transfer 2500 to account 1234567890"
    - "Check balance"
    - "Show transactions"
    """
    
    # Number words to digits mapping
    NUMBER_WORDS = {
        'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4,
        'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9,
        'ten': 10, 'eleven': 11, 'twelve': 12, 'thirteen': 13,
        'fourteen': 14, 'fifteen': 15, 'sixteen': 16, 'seventeen': 17,
        'eighteen': 18, 'nineteen': 19, 'twenty': 20, 'thirty': 30,
        'forty': 40, 'fifty': 50, 'sixty': 60, 'seventy': 70,
        'eighty': 80, 'ninety': 90, 'hundred': 100, 'thousand': 1000,
        'lakh': 100000, 'lac': 100000, 'crore': 10000000
    }
    
    # Payment command patterns
    PAYMENT_PATTERNS = [
        r'(?:send|pay|transfer)\s+(?:rs\.?|rupees?)?\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:rs\.?|rupees?)?\s*to\s+(.+)',
        r'(?:send|pay|transfer)\s+(.+?)\s+(?:rs\.?|rupees?)?\s*(\d+(?:,\d+)*(?:\.\d+)?)',
        r'(?:send|pay|transfer)\s+(\w+(?:\s+\w+)*)\s+to\s+(.+)',
    ]
    
    BALANCE_PATTERNS = [
        r'(?:check|show|what\'?s?\s+(?:is\s+)?my|get)\s*balance',
        r'(?:how\s+much\s+)?(?:money\s+)?(?:do\s+i\s+have|in\s+(?:my\s+)?account)',
        r'balance\s*(?:check|inquiry)?'
    ]
    
    TRANSACTION_PATTERNS = [
        r'(?:show|get|list|display)\s*(?:my\s+)?(?:recent\s+)?transactions?',
        r'(?:transaction|payment)\s*history',
        r'(?:what\s+are\s+)?(?:my\s+)?(?:recent\s+)?(?:transactions?|payments?)'
    ]
    
    REQUEST_MONEY_PATTERNS = [
        r'(?:request|ask\s+for)\s+(?:rs\.?|rupees?)?\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:rs\.?|rupees?)?\s*from\s+(.+)',
        r'(?:request|ask)\s+(.+?)\s+(?:for\s+)?(?:rs\.?|rupees?)?\s*(\d+(?:,\d+)*(?:\.\d+)?)'
    ]
    
    def __init__(self):
        self.contacts_cache = {}  # Cache for contact name to ID mapping
    
    def parse_command(self, text):
        """
        Parse a voice command and extract intent and parameters
        
        Args:
            text: str - Transcribed voice command
            
        Returns:
            dict with:
                - intent: str (payment, balance, transactions, request_money, unknown)
                - params: dict with extracted parameters
                - confidence: float (0-1)
                - original_text: str
        """
        text = text.lower().strip()
        
        # Try to parse as payment command
        payment_result = self._parse_payment(text)
        if payment_result:
            return payment_result
        
        # Try to parse as balance check
        if self._matches_pattern(text, self.BALANCE_PATTERNS):
            return {
                'intent': 'balance',
                'params': {},
                'confidence': 0.9,
                'original_text': text
            }
        
        # Try to parse as transaction history
        if self._matches_pattern(text, self.TRANSACTION_PATTERNS):
            return {
                'intent': 'transactions',
                'params': {},
                'confidence': 0.9,
                'original_text': text
            }
        
        # Try to parse as money request
        request_result = self._parse_request_money(text)
        if request_result:
            return request_result
        
        return {
            'intent': 'unknown',
            'params': {},
            'confidence': 0.0,
            'original_text': text,
            'message': 'Could not understand the command. Try saying "Send [amount] to [name]" or "Check balance"'
        }
    
    def _parse_payment(self, text):
        """Parse payment commands"""
        for pattern in self.PAYMENT_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                groups = match.groups()
                
                # Determine which group is amount and which is recipient
                amount = None
                recipient = None
                
                for group in groups:
                    if group:
                        # Check if it's a number
                        cleaned = group.replace(',', '').strip()
                        try:
                            amount = float(cleaned)
                        except ValueError:
                            # Try to parse word numbers
                            parsed_amount = self._parse_word_numbers(group)
                            if parsed_amount:
                                amount = parsed_amount
                            else:
                                recipient = group.strip()
                
                if amount and recipient:
                    return {
                        'intent': 'payment',
                        'params': {
                            'amount': amount,
                            'recipient': recipient,
                            'recipient_type': self._determine_recipient_type(recipient)
                        },
                        'confidence': 0.85,
                        'original_text': text
                    }
        
        return None
    
    def _parse_request_money(self, text):
        """Parse money request commands"""
        for pattern in self.REQUEST_MONEY_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                groups = match.groups()
                
                amount = None
                sender = None
                
                for group in groups:
                    if group:
                        cleaned = group.replace(',', '').strip()
                        try:
                            amount = float(cleaned)
                        except ValueError:
                            parsed_amount = self._parse_word_numbers(group)
                            if parsed_amount:
                                amount = parsed_amount
                            else:
                                sender = group.strip()
                
                if amount and sender:
                    return {
                        'intent': 'request_money',
                        'params': {
                            'amount': amount,
                            'from_user': sender
                        },
                        'confidence': 0.8,
                        'original_text': text
                    }
        
        return None
    
    def _matches_pattern(self, text, patterns):
        """Check if text matches any of the patterns"""
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False
    
    def _parse_word_numbers(self, text):
        """Convert word numbers to digits"""
        words = text.lower().split()
        total = 0
        current = 0
        
        for word in words:
            if word in self.NUMBER_WORDS:
                value = self.NUMBER_WORDS[word]
                if value >= 1000:
                    if current == 0:
                        current = 1
                    current *= value
                    total += current
                    current = 0
                elif value >= 100:
                    if current == 0:
                        current = 1
                    current *= value
                else:
                    current += value
        
        total += current
        return total if total > 0 else None
    
    def _determine_recipient_type(self, recipient):
        """Determine if recipient is a name, phone, UPI ID, or account number"""
        # Check if it's a phone number
        if re.match(r'^\d{10}$', recipient.replace(' ', '')):
            return 'phone'
        
        # Check if it's a UPI ID
        if '@' in recipient:
            return 'upi_id'
        
        # Check if it's an account number
        if re.match(r'^\d{9,18}$', recipient.replace(' ', '')):
            return 'account_number'
        
        # Default to name
        return 'name'
    
    def set_contacts_cache(self, contacts):
        """Set contacts cache for name resolution"""
        self.contacts_cache = contacts


class SpeechRecognitionService:
    """
    Speech Recognition Service using Google Speech API
    """
    
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.parser = VoicePaymentParser()
        
        # Adjust for ambient noise
        self.recognizer.energy_threshold = 4000
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 0.8
    
    def recognize_from_microphone(self, timeout=5, phrase_time_limit=10):
        """
        Recognize speech from microphone
        
        Args:
            timeout: seconds to wait for phrase to start
            phrase_time_limit: maximum seconds for phrase
            
        Returns:
            dict with recognition result
        """
        try:
            with sr.Microphone() as source:
                # Adjust for ambient noise
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                
                print("Listening...")
                audio = self.recognizer.listen(
                    source, 
                    timeout=timeout,
                    phrase_time_limit=phrase_time_limit
                )
                
                # Recognize using Google Speech API
                text = self.recognizer.recognize_google(audio, language='en-IN')
                
                # Parse the command
                parsed = self.parser.parse_command(text)
                
                return {
                    'success': True,
                    'text': text,
                    'parsed': parsed,
                    'timestamp': datetime.utcnow().isoformat()
                }
                
        except sr.WaitTimeoutError:
            return {
                'success': False,
                'error': 'timeout',
                'message': 'No speech detected. Please try again.'
            }
        except sr.UnknownValueError:
            return {
                'success': False,
                'error': 'unrecognized',
                'message': 'Could not understand the audio. Please speak clearly.'
            }
        except sr.RequestError as e:
            return {
                'success': False,
                'error': 'service_error',
                'message': f'Speech recognition service error: {str(e)}'
            }
        except Exception as e:
            return {
                'success': False,
                'error': 'unknown',
                'message': str(e)
            }
    
    def recognize_from_audio_data(self, audio_data, sample_rate=16000, sample_width=2):
        """
        Recognize speech from audio data bytes
        
        Args:
            audio_data: bytes - Raw audio data
            sample_rate: int - Audio sample rate
            sample_width: int - Audio sample width in bytes
            
        Returns:
            dict with recognition result
        """
        try:
            audio = sr.AudioData(audio_data, sample_rate, sample_width)
            
            # Recognize using Google Speech API
            text = self.recognizer.recognize_google(audio, language='en-IN')
            
            # Parse the command
            parsed = self.parser.parse_command(text)
            
            return {
                'success': True,
                'text': text,
                'parsed': parsed,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except sr.UnknownValueError:
            return {
                'success': False,
                'error': 'unrecognized',
                'message': 'Could not understand the audio.'
            }
        except sr.RequestError as e:
            return {
                'success': False,
                'error': 'service_error',
                'message': f'Speech recognition service error: {str(e)}'
            }
        except Exception as e:
            return {
                'success': False,
                'error': 'unknown',
                'message': str(e)
            }
    
    def parse_text_command(self, text):
        """
        Parse a text command (for testing or text-based input)
        
        Args:
            text: str - Command text
            
        Returns:
            dict with parsed command
        """
        return self.parser.parse_command(text)
    
    def set_contacts(self, contacts):
        """Set contacts for name resolution"""
        self.parser.set_contacts_cache(contacts)
    
    def get_supported_commands(self):
        """Get list of supported voice commands"""
        return {
            'payment': [
                'Send [amount] to [name/phone/UPI]',
                'Pay [amount] to [name]',
                'Transfer [amount] to [name]'
            ],
            'balance': [
                'Check balance',
                'What is my balance',
                'Show balance'
            ],
            'transactions': [
                'Show transactions',
                'Recent transactions',
                'Transaction history'
            ],
            'request_money': [
                'Request [amount] from [name]',
                'Ask [name] for [amount]'
            ]
        }


# Global instance
speech_service = SpeechRecognitionService()
