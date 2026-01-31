"""
Blockchain Service for Secure Transactions
Implements a simple blockchain for transaction integrity and QR code generation
"""
import hashlib
import json
import time
import qrcode
import io
import base64
import secrets
from datetime import datetime, timedelta
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from Crypto.Random import get_random_bytes


class Block:
    """Individual block in the blockchain"""
    
    def __init__(self, index, timestamp, transactions, proof, previous_hash):
        self.index = index
        self.timestamp = timestamp
        self.transactions = transactions
        self.proof = proof
        self.previous_hash = previous_hash
        self.hash = self.calculate_hash()
    
    def calculate_hash(self):
        """Calculate SHA-256 hash of the block"""
        block_string = json.dumps({
            'index': self.index,
            'timestamp': str(self.timestamp),
            'transactions': self.transactions,
            'proof': self.proof,
            'previous_hash': self.previous_hash
        }, sort_keys=True).encode()
        
        return hashlib.sha256(block_string).hexdigest()
    
    def to_dict(self):
        return {
            'index': self.index,
            'timestamp': str(self.timestamp),
            'transactions': self.transactions,
            'proof': self.proof,
            'previous_hash': self.previous_hash,
            'hash': self.hash
        }


class Blockchain:
    """Simple blockchain implementation for transaction integrity"""
    
    def __init__(self, difficulty=4):
        self.chain = []
        self.pending_transactions = []
        self.difficulty = difficulty
        
        # Create genesis block
        self.create_genesis_block()
    
    def create_genesis_block(self):
        """Create the first block in the chain"""
        genesis_block = Block(
            index=0,
            timestamp=datetime.utcnow(),
            transactions=['Genesis Block - SecureBank Initialized'],
            proof=0,
            previous_hash='0' * 64
        )
        self.chain.append(genesis_block)
    
    def get_latest_block(self):
        """Get the most recent block"""
        return self.chain[-1]
    
    def add_transaction(self, transaction_data):
        """Add a transaction to pending transactions"""
        transaction_hash = self.hash_transaction(transaction_data)
        self.pending_transactions.append({
            'data': transaction_data,
            'hash': transaction_hash,
            'timestamp': datetime.utcnow().isoformat()
        })
        return transaction_hash
    
    def hash_transaction(self, transaction_data):
        """Create a unique hash for a transaction"""
        tx_string = json.dumps(transaction_data, sort_keys=True).encode()
        return hashlib.sha256(tx_string).hexdigest()
    
    def proof_of_work(self, previous_proof):
        """Simple proof of work algorithm"""
        new_proof = 0
        while not self.is_valid_proof(previous_proof, new_proof):
            new_proof += 1
        return new_proof
    
    def is_valid_proof(self, previous_proof, current_proof):
        """Check if proof is valid"""
        guess = f'{previous_proof}{current_proof}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[:self.difficulty] == '0' * self.difficulty
    
    def mine_block(self):
        """Mine a new block with pending transactions"""
        if not self.pending_transactions:
            return None
        
        previous_block = self.get_latest_block()
        proof = self.proof_of_work(previous_block.proof)
        
        new_block = Block(
            index=len(self.chain),
            timestamp=datetime.utcnow(),
            transactions=[tx['hash'] for tx in self.pending_transactions],
            proof=proof,
            previous_hash=previous_block.hash
        )
        
        self.chain.append(new_block)
        self.pending_transactions = []
        
        return new_block
    
    def is_chain_valid(self):
        """Validate the entire blockchain"""
        for i in range(1, len(self.chain)):
            current_block = self.chain[i]
            previous_block = self.chain[i - 1]
            
            # Check hash
            if current_block.hash != current_block.calculate_hash():
                return False
            
            # Check previous hash reference
            if current_block.previous_hash != previous_block.hash:
                return False
            
            # Check proof of work
            if not self.is_valid_proof(previous_block.proof, current_block.proof):
                return False
        
        return True
    
    def get_chain(self):
        """Get the full blockchain"""
        return [block.to_dict() for block in self.chain]
    
    def verify_transaction(self, transaction_hash):
        """Verify if a transaction exists in the blockchain"""
        for block in self.chain:
            if transaction_hash in block.transactions:
                return {
                    'verified': True,
                    'block_index': block.index,
                    'block_hash': block.hash,
                    'timestamp': str(block.timestamp)
                }
        
        # Check pending transactions
        for tx in self.pending_transactions:
            if tx['hash'] == transaction_hash:
                return {
                    'verified': True,
                    'status': 'pending',
                    'timestamp': tx['timestamp']
                }
        
        return {'verified': False}


class SecureQRGenerator:
    """
    Secure QR Code Generator with blockchain integration
    """
    
    def __init__(self, encryption_key=None):
        # 32-byte key for AES-256
        self.encryption_key = encryption_key or get_random_bytes(32)
    
    def generate_payment_qr(self, payment_data, blockchain_hash=None):
        """
        Generate a secure QR code for payment
        
        Args:
            payment_data: dict containing:
                - receiver_id: str
                - receiver_upi: str
                - amount: float (optional for dynamic)
                - description: str
                - expires_in_minutes: int
        
        Returns:
            dict with QR code image (base64) and metadata
        """
        # Generate unique payment ID and nonce
        payment_id = secrets.token_hex(16)
        nonce = secrets.token_hex(16)
        timestamp = datetime.utcnow().isoformat()
        
        # Calculate expiry
        expires_in = payment_data.get('expires_in_minutes', 5)
        expires_at = datetime.utcnow() + timedelta(minutes=expires_in)
        
        # Create payment payload
        payload = {
            'payment_id': payment_id,
            'receiver_id': payment_data.get('receiver_id'),
            'receiver_upi': payment_data.get('receiver_upi'),
            'amount': payment_data.get('amount'),
            'description': payment_data.get('description', ''),
            'timestamp': timestamp,
            'expires_at': expires_at.isoformat(),
            'nonce': nonce,
            'blockchain_hash': blockchain_hash
        }
        
        # Create signature (hash of payload)
        signature = self._create_signature(payload)
        payload['signature'] = signature
        
        # Encrypt the payload
        encrypted_data = self._encrypt_payload(payload)
        
        # Create QR code data
        qr_data = {
            'type': 'securebank_payment',
            'version': '1.0',
            'data': encrypted_data,
            'hash': hashlib.sha256(encrypted_data.encode()).hexdigest()[:16]
        }
        
        # Generate QR code image
        qr_image_base64 = self._generate_qr_image(json.dumps(qr_data))
        
        return {
            'payment_id': payment_id,
            'qr_code_image': qr_image_base64,
            'qr_code_data': json.dumps(qr_data),
            'qr_code_hash': qr_data['hash'],
            'signature': signature,
            'nonce': nonce,
            'expires_at': expires_at.isoformat(),
            'payload': payload  # For database storage
        }
    
    def _create_signature(self, payload):
        """Create a cryptographic signature for the payload"""
        payload_string = json.dumps(payload, sort_keys=True).encode()
        signature = hashlib.sha256(payload_string + self.encryption_key).hexdigest()
        return signature
    
    def _encrypt_payload(self, payload):
        """Encrypt payload using AES-256-CBC"""
        try:
            iv = get_random_bytes(16)
            cipher = AES.new(self.encryption_key, AES.MODE_CBC, iv)
            
            payload_bytes = json.dumps(payload).encode('utf-8')
            encrypted = cipher.encrypt(pad(payload_bytes, AES.block_size))
            
            # Combine IV and encrypted data
            combined = iv + encrypted
            return base64.b64encode(combined).decode('utf-8')
        except Exception as e:
            # Fallback to base64 encoding if encryption fails
            return base64.b64encode(json.dumps(payload).encode()).decode('utf-8')
    
    def decrypt_payload(self, encrypted_data):
        """Decrypt QR code payload"""
        try:
            combined = base64.b64decode(encrypted_data)
            iv = combined[:16]
            encrypted = combined[16:]
            
            cipher = AES.new(self.encryption_key, AES.MODE_CBC, iv)
            decrypted = unpad(cipher.decrypt(encrypted), AES.block_size)
            
            return json.loads(decrypted.decode('utf-8'))
        except Exception as e:
            # Try base64 decoding as fallback
            try:
                decoded = base64.b64decode(encrypted_data)
                return json.loads(decoded.decode('utf-8'))
            except:
                return None
    
    def _generate_qr_image(self, data):
        """Generate QR code image and return as base64"""
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        return base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    def verify_qr_payment(self, qr_data_string):
        """
        Verify and decode a scanned QR code
        
        Args:
            qr_data_string: JSON string from scanned QR code
            
        Returns:
            dict with verification result and payment data
        """
        try:
            qr_data = json.loads(qr_data_string)
            
            # Verify QR code type
            if qr_data.get('type') != 'securebank_payment':
                return {'valid': False, 'error': 'Invalid QR code type'}
            
            # Verify hash
            calculated_hash = hashlib.sha256(qr_data['data'].encode()).hexdigest()[:16]
            if calculated_hash != qr_data.get('hash'):
                return {'valid': False, 'error': 'QR code integrity check failed'}
            
            # Decrypt payload
            payload = self.decrypt_payload(qr_data['data'])
            if not payload:
                return {'valid': False, 'error': 'Failed to decrypt QR code'}
            
            # Check expiry
            expires_at = datetime.fromisoformat(payload['expires_at'])
            if datetime.utcnow() > expires_at:
                return {'valid': False, 'error': 'QR code has expired'}
            
            # Verify signature
            signature = payload.pop('signature', None)
            expected_signature = self._create_signature(payload)
            if signature != expected_signature:
                return {'valid': False, 'error': 'Invalid signature'}
            
            payload['signature'] = signature
            
            return {
                'valid': True,
                'payment_data': payload
            }
            
        except json.JSONDecodeError:
            return {'valid': False, 'error': 'Invalid QR code format'}
        except Exception as e:
            return {'valid': False, 'error': str(e)}
    
    def generate_upi_qr(self, upi_id, name, amount=None, note=None):
        """
        Generate a UPI-compatible QR code
        
        Args:
            upi_id: str - UPI ID of receiver
            name: str - Name of receiver
            amount: float - Payment amount (optional)
            note: str - Transaction note (optional)
        """
        # UPI payment URL format
        upi_url = f"upi://pay?pa={upi_id}&pn={name}"
        
        if amount:
            upi_url += f"&am={amount}"
        if note:
            upi_url += f"&tn={note}"
        
        # Add transaction reference
        txn_ref = secrets.token_hex(8)
        upi_url += f"&tr={txn_ref}"
        
        # Generate QR code
        qr_image = self._generate_qr_image(upi_url)
        
        return {
            'upi_url': upi_url,
            'qr_code_image': qr_image,
            'transaction_ref': txn_ref
        }


# Global instances
blockchain = Blockchain(difficulty=4)
qr_generator = SecureQRGenerator()
