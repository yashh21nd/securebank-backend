"""
Database Models for SecureBank
"""
from datetime import datetime
from app import db
import uuid


def generate_uuid():
    return str(uuid.uuid4())


class User(db.Model):
    """User model for authentication and account management"""
    __tablename__ = 'users'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(15), unique=True, nullable=True)
    full_name = db.Column(db.String(150), nullable=True)
    upi_id = db.Column(db.String(100), unique=True, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    accounts = db.relationship('Account', backref='user', lazy=True)
    sent_transactions = db.relationship('Transaction', foreign_keys='Transaction.sender_id', backref='sender', lazy=True)
    received_transactions = db.relationship('Transaction', foreign_keys='Transaction.receiver_id', backref='receiver', lazy=True)
    notifications = db.relationship('Notification', backref='user', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'phone': self.phone,
            'full_name': self.full_name,
            'upi_id': self.upi_id,
            'created_at': self.created_at.isoformat(),
            'is_active': self.is_active
        }


class Account(db.Model):
    """Bank account model"""
    __tablename__ = 'accounts'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    account_number = db.Column(db.String(20), unique=True, nullable=False)
    account_type = db.Column(db.String(20), default='savings')  # savings, current
    balance = db.Column(db.Float, default=0.0)
    currency = db.Column(db.String(3), default='INR')
    is_primary = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'account_number': self.account_number,
            'account_type': self.account_type,
            'balance': self.balance,
            'currency': self.currency,
            'is_primary': self.is_primary,
            'created_at': self.created_at.isoformat()
        }


class Transaction(db.Model):
    """Transaction model for all money transfers"""
    __tablename__ = 'transactions'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    transaction_id = db.Column(db.String(50), unique=True, nullable=False)
    sender_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=True)
    receiver_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=True)
    sender_account_id = db.Column(db.String(36), db.ForeignKey('accounts.id'), nullable=True)
    receiver_account_id = db.Column(db.String(36), db.ForeignKey('accounts.id'), nullable=True)
    
    transaction_type = db.Column(db.String(20), nullable=False)  # PAYMENT, TRANSFER, CASH_OUT, CASH_IN, DEBIT
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), default='INR')
    
    sender_balance_before = db.Column(db.Float, nullable=True)
    sender_balance_after = db.Column(db.Float, nullable=True)
    receiver_balance_before = db.Column(db.Float, nullable=True)
    receiver_balance_after = db.Column(db.Float, nullable=True)
    
    description = db.Column(db.String(500), nullable=True)
    category = db.Column(db.String(50), nullable=True)
    
    status = db.Column(db.String(20), default='pending')  # pending, completed, failed, flagged, cancelled
    
    # Fraud detection
    fraud_score = db.Column(db.Float, default=0.0)
    is_fraudulent = db.Column(db.Boolean, default=False)
    is_flagged = db.Column(db.Boolean, default=False)
    
    # Blockchain reference
    blockchain_hash = db.Column(db.String(64), nullable=True)
    block_index = db.Column(db.Integer, nullable=True)
    
    # QR Payment reference
    qr_payment_id = db.Column(db.String(36), nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'transaction_id': self.transaction_id,
            'sender_id': self.sender_id,
            'receiver_id': self.receiver_id,
            'transaction_type': self.transaction_type,
            'amount': self.amount,
            'currency': self.currency,
            'sender_balance_before': self.sender_balance_before,
            'sender_balance_after': self.sender_balance_after,
            'receiver_balance_before': self.receiver_balance_before,
            'receiver_balance_after': self.receiver_balance_after,
            'description': self.description,
            'category': self.category,
            'status': self.status,
            'fraud_score': self.fraud_score,
            'is_fraudulent': self.is_fraudulent,
            'is_flagged': self.is_flagged,
            'blockchain_hash': self.blockchain_hash,
            'created_at': self.created_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }


class QRPayment(db.Model):
    """QR Code payment model for secure blockchain-based payments"""
    __tablename__ = 'qr_payments'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    creator_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Float, nullable=True)  # Nullable for dynamic amount
    description = db.Column(db.String(500), nullable=True)
    
    # QR Code data
    qr_code_hash = db.Column(db.String(64), unique=True, nullable=False)
    qr_code_data = db.Column(db.Text, nullable=False)  # Encrypted payment data
    
    # Blockchain security
    blockchain_signature = db.Column(db.String(256), nullable=False)
    nonce = db.Column(db.String(32), nullable=False)
    
    # Status
    status = db.Column(db.String(20), default='active')  # active, used, expired, cancelled
    is_single_use = db.Column(db.Boolean, default=True)
    
    # Expiry
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)
    used_by = db.Column(db.String(36), nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'creator_id': self.creator_id,
            'amount': self.amount,
            'description': self.description,
            'qr_code_hash': self.qr_code_hash,
            'status': self.status,
            'is_single_use': self.is_single_use,
            'expires_at': self.expires_at.isoformat(),
            'used_at': self.used_at.isoformat() if self.used_at else None,
            'created_at': self.created_at.isoformat()
        }


class Notification(db.Model):
    """Notification model for real-time alerts"""
    __tablename__ = 'notifications'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    
    notification_type = db.Column(db.String(50), nullable=False)  # payment_received, payment_sent, fraud_alert, etc.
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    data = db.Column(db.JSON, nullable=True)  # Additional data like transaction details
    
    is_read = db.Column(db.Boolean, default=False)
    is_popup = db.Column(db.Boolean, default=True)  # Show as popup
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    read_at = db.Column(db.DateTime, nullable=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'notification_type': self.notification_type,
            'title': self.title,
            'message': self.message,
            'data': self.data,
            'is_read': self.is_read,
            'is_popup': self.is_popup,
            'created_at': self.created_at.isoformat(),
            'read_at': self.read_at.isoformat() if self.read_at else None
        }


class FraudAlert(db.Model):
    """Fraud alert model for tracking detected fraud"""
    __tablename__ = 'fraud_alerts'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    transaction_id = db.Column(db.String(36), db.ForeignKey('transactions.id'), nullable=False)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    
    fraud_score = db.Column(db.Float, nullable=False)
    fraud_type = db.Column(db.String(50), nullable=True)  # anomaly, pattern, velocity, etc.
    reason = db.Column(db.Text, nullable=True)
    
    status = db.Column(db.String(20), default='pending')  # pending, reviewed, confirmed, dismissed
    reviewed_by = db.Column(db.String(36), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'transaction_id': self.transaction_id,
            'user_id': self.user_id,
            'fraud_score': self.fraud_score,
            'fraud_type': self.fraud_type,
            'reason': self.reason,
            'status': self.status,
            'created_at': self.created_at.isoformat()
        }


class FraudTrainingData(db.Model):
    """Store fraud detection training data from PaySim dataset"""
    __tablename__ = 'fraud_training_data'
    
    id = db.Column(db.Integer, primary_key=True)
    step = db.Column(db.Integer, nullable=False)  # Time step (1 step = 1 hour)
    transaction_type = db.Column(db.String(20), nullable=False)  # TRANSFER, CASH_OUT, etc.
    amount = db.Column(db.Float, nullable=False)
    name_orig = db.Column(db.String(50), nullable=False)  # Sender ID
    old_balance_orig = db.Column(db.Float, nullable=False)  # Sender's balance before
    new_balance_orig = db.Column(db.Float, nullable=False)  # Sender's balance after
    name_dest = db.Column(db.String(50), nullable=False)  # Receiver ID
    old_balance_dest = db.Column(db.Float, nullable=False)  # Receiver's balance before
    new_balance_dest = db.Column(db.Float, nullable=False)  # Receiver's balance after
    is_fraud = db.Column(db.Boolean, nullable=False)  # Target: 1 if fraud, 0 otherwise
    is_flagged_fraud = db.Column(db.Boolean, default=False)  # Flagged by system
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'step': self.step,
            'type': self.transaction_type,
            'amount': self.amount,
            'nameOrig': self.name_orig,
            'oldbalanceOrg': self.old_balance_orig,
            'newbalanceOrig': self.new_balance_orig,
            'nameDest': self.name_dest,
            'oldbalanceDest': self.old_balance_dest,
            'newbalanceDest': self.new_balance_dest,
            'isFraud': self.is_fraud,
            'isFlaggedFraud': self.is_flagged_fraud
        }


class BlockchainBlock(db.Model):
    """Blockchain block model for transaction integrity"""
    __tablename__ = 'blockchain_blocks'
    
    id = db.Column(db.Integer, primary_key=True)
    index = db.Column(db.Integer, unique=True, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False)
    transactions = db.Column(db.JSON, nullable=False)  # List of transaction hashes
    proof = db.Column(db.Integer, nullable=False)
    previous_hash = db.Column(db.String(64), nullable=False)
    current_hash = db.Column(db.String(64), unique=True, nullable=False)
    
    def to_dict(self):
        return {
            'index': self.index,
            'timestamp': self.timestamp.isoformat(),
            'transactions': self.transactions,
            'proof': self.proof,
            'previous_hash': self.previous_hash,
            'current_hash': self.current_hash
        }
