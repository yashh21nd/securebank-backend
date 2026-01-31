"""
Payment Routes
Handles money transfers, payments, and real-time balance updates
"""
from flask import Blueprint, request, jsonify
from datetime import datetime
import uuid
from app.routes.auth import token_required

payments_bp = Blueprint('payments', __name__)


def get_db():
    from app import db
    return db


def get_models():
    from app.models import Transaction, Account, User, Notification
    return Transaction, Account, User, Notification


def get_services():
    from app.services.fraud_detection import fraud_service
    from app.services.blockchain import blockchain
    return fraud_service, blockchain


def get_notification_emitter():
    from app.websocket import get_notification_emitter
    return get_notification_emitter()


def generate_transaction_id():
    """Generate unique transaction ID"""
    return f"TXN{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:8].upper()}"


@payments_bp.route('/send', methods=['POST'])
@token_required
def send_money(current_user):
    """
    Send money to another user
    Includes fraud detection and real-time notifications
    """
    data = request.get_json()
    db = get_db()
    Transaction, Account, User, Notification = get_models()
    fraud_service, blockchain = get_services()
    
    # Validate required fields
    if not data.get('amount'):
        return jsonify({'error': 'Amount is required'}), 400
    
    if not data.get('receiver_id') and not data.get('upi_id') and not data.get('phone'):
        return jsonify({'error': 'Receiver ID, UPI ID, or phone is required'}), 400
    
    amount = float(data['amount'])
    if amount <= 0:
        return jsonify({'error': 'Amount must be positive'}), 400
    
    # Find receiver
    receiver = None
    if data.get('receiver_id'):
        receiver = User.query.get(data['receiver_id'])
    elif data.get('upi_id'):
        receiver = User.query.filter_by(upi_id=data['upi_id']).first()
    elif data.get('phone'):
        receiver = User.query.filter_by(phone=data['phone']).first()
    
    if not receiver:
        return jsonify({'error': 'Receiver not found'}), 404
    
    if receiver.id == current_user.id:
        return jsonify({'error': 'Cannot send money to yourself'}), 400
    
    # Get sender's primary account
    sender_account = Account.query.filter_by(user_id=current_user.id, is_primary=True).first()
    if not sender_account:
        return jsonify({'error': 'No active account found'}), 400
    
    # Check balance
    if sender_account.balance < amount:
        return jsonify({'error': 'Insufficient balance'}), 400
    
    # Get receiver's primary account
    receiver_account = Account.query.filter_by(user_id=receiver.id, is_primary=True).first()
    if not receiver_account:
        return jsonify({'error': 'Receiver account not found'}), 400
    
    # Fraud detection
    fraud_check = fraud_service.predict_fraud({
        'type': 'TRANSFER',
        'amount': amount,
        'oldbalanceOrg': sender_account.balance,
        'newbalanceOrig': sender_account.balance - amount,
        'oldbalanceDest': receiver_account.balance,
        'newbalanceDest': receiver_account.balance + amount,
        'step': datetime.utcnow().hour
    })
    
    # Block high-risk transactions
    if fraud_check.get('should_block'):
        # Create blocked transaction record
        transaction = Transaction(
            id=str(uuid.uuid4()),
            transaction_id=generate_transaction_id(),
            sender_id=current_user.id,
            receiver_id=receiver.id,
            sender_account_id=sender_account.id,
            receiver_account_id=receiver_account.id,
            transaction_type='TRANSFER',
            amount=amount,
            sender_balance_before=sender_account.balance,
            sender_balance_after=sender_account.balance,
            receiver_balance_before=receiver_account.balance,
            receiver_balance_after=receiver_account.balance,
            description=data.get('description', ''),
            category=data.get('category', 'Transfer'),
            status='blocked',
            fraud_score=fraud_check['fraud_probability'],
            is_fraudulent=True,
            is_flagged=True
        )
        
        db.session.add(transaction)
        db.session.commit()
        
        # Send fraud alert notification
        emitter = get_notification_emitter()
        if emitter:
            emitter.emit_fraud_alert(current_user.id, {
                'transaction_id': transaction.transaction_id,
                'amount': amount,
                'fraud_score': fraud_check['fraud_probability'],
                'risk_level': fraud_check['risk_level'],
                'risk_factors': fraud_check['risk_factors']
            })
        
        return jsonify({
            'error': 'Transaction blocked due to suspicious activity',
            'fraud_alert': {
                'risk_level': fraud_check['risk_level'],
                'risk_factors': fraud_check['risk_factors']
            }
        }), 403
    
    try:
        # Store balances before transaction
        sender_balance_before = sender_account.balance
        receiver_balance_before = receiver_account.balance
        
        # Update balances
        sender_account.balance -= amount
        receiver_account.balance += amount
        
        # Add to blockchain
        tx_hash = blockchain.add_transaction({
            'sender': current_user.id,
            'receiver': receiver.id,
            'amount': amount,
            'timestamp': datetime.utcnow().isoformat()
        })
        
        # Create transaction record
        transaction = Transaction(
            id=str(uuid.uuid4()),
            transaction_id=generate_transaction_id(),
            sender_id=current_user.id,
            receiver_id=receiver.id,
            sender_account_id=sender_account.id,
            receiver_account_id=receiver_account.id,
            transaction_type='TRANSFER',
            amount=amount,
            sender_balance_before=sender_balance_before,
            sender_balance_after=sender_account.balance,
            receiver_balance_before=receiver_balance_before,
            receiver_balance_after=receiver_account.balance,
            description=data.get('description', ''),
            category=data.get('category', 'Transfer'),
            status='completed',
            fraud_score=fraud_check['fraud_probability'],
            is_fraudulent=False,
            is_flagged=fraud_check.get('should_flag', False),
            blockchain_hash=tx_hash,
            completed_at=datetime.utcnow()
        )
        
        db.session.add(transaction)
        
        # Create notifications
        # For sender
        sender_notification = Notification(
            id=str(uuid.uuid4()),
            user_id=current_user.id,
            notification_type='payment_sent',
            title='Payment Sent',
            message=f'₹{amount:.2f} sent to {receiver.full_name or receiver.username}',
            data={
                'transaction_id': transaction.transaction_id,
                'amount': amount,
                'receiver_name': receiver.full_name or receiver.username
            }
        )
        
        # For receiver
        receiver_notification = Notification(
            id=str(uuid.uuid4()),
            user_id=receiver.id,
            notification_type='payment_received',
            title='Payment Received',
            message=f'₹{amount:.2f} received from {current_user.full_name or current_user.username}',
            data={
                'transaction_id': transaction.transaction_id,
                'amount': amount,
                'sender_name': current_user.full_name or current_user.username
            },
            is_popup=True
        )
        
        db.session.add(sender_notification)
        db.session.add(receiver_notification)
        
        db.session.commit()
        
        # Send real-time notifications
        emitter = get_notification_emitter()
        if emitter:
            # Notify receiver (popup)
            emitter.emit_payment_received(receiver.id, {
                'transaction_id': transaction.transaction_id,
                'amount': amount,
                'sender_id': current_user.id,
                'sender_name': current_user.full_name or current_user.username,
                'description': data.get('description', '')
            })
            
            # Notify sender
            emitter.emit_payment_sent(current_user.id, {
                'transaction_id': transaction.transaction_id,
                'amount': amount,
                'receiver_id': receiver.id,
                'receiver_name': receiver.full_name or receiver.username,
                'new_balance': sender_account.balance
            })
            
            # Send balance updates
            emitter.emit_balance_update(sender_account.id, current_user.id, {
                'previous_balance': sender_balance_before,
                'current_balance': sender_account.balance,
                'change': -amount
            })
            
            emitter.emit_balance_update(receiver_account.id, receiver.id, {
                'previous_balance': receiver_balance_before,
                'current_balance': receiver_account.balance,
                'change': amount
            })
        
        return jsonify({
            'message': 'Payment successful',
            'transaction': transaction.to_dict(),
            'new_balance': sender_account.balance,
            'fraud_check': {
                'risk_level': fraud_check['risk_level'],
                'was_flagged': fraud_check.get('should_flag', False)
            }
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@payments_bp.route('/request', methods=['POST'])
@token_required
def request_money(current_user):
    """Request money from another user"""
    data = request.get_json()
    db = get_db()
    Transaction, Account, User, Notification = get_models()
    
    if not data.get('amount'):
        return jsonify({'error': 'Amount is required'}), 400
    
    if not data.get('from_user_id') and not data.get('upi_id') and not data.get('phone'):
        return jsonify({'error': 'User ID, UPI ID, or phone is required'}), 400
    
    amount = float(data['amount'])
    if amount <= 0:
        return jsonify({'error': 'Amount must be positive'}), 400
    
    # Find the user to request from
    from_user = None
    if data.get('from_user_id'):
        from_user = User.query.get(data['from_user_id'])
    elif data.get('upi_id'):
        from_user = User.query.filter_by(upi_id=data['upi_id']).first()
    elif data.get('phone'):
        from_user = User.query.filter_by(phone=data['phone']).first()
    
    if not from_user:
        return jsonify({'error': 'User not found'}), 404
    
    if from_user.id == current_user.id:
        return jsonify({'error': 'Cannot request money from yourself'}), 400
    
    # Create money request notification
    request_id = str(uuid.uuid4())
    notification = Notification(
        id=str(uuid.uuid4()),
        user_id=from_user.id,
        notification_type='money_request',
        title='Money Request',
        message=f'{current_user.full_name or current_user.username} requested ₹{amount:.2f}',
        data={
            'request_id': request_id,
            'amount': amount,
            'requester_id': current_user.id,
            'requester_name': current_user.full_name or current_user.username,
            'requester_upi': current_user.upi_id,
            'note': data.get('note', '')
        },
        is_popup=True
    )
    
    db.session.add(notification)
    db.session.commit()
    
    # Send real-time notification
    emitter = get_notification_emitter()
    if emitter:
        emitter.emit_money_request(from_user.id, {
            'request_id': request_id,
            'amount': amount,
            'requester_id': current_user.id,
            'requester_name': current_user.full_name or current_user.username,
            'note': data.get('note', '')
        })
    
    return jsonify({
        'message': 'Money request sent',
        'request_id': request_id
    }), 200


@payments_bp.route('/balance', methods=['GET'])
@token_required
def get_balance(current_user):
    """Get current account balance"""
    Transaction, Account, User, Notification = get_models()
    
    accounts = Account.query.filter_by(user_id=current_user.id).all()
    
    return jsonify({
        'accounts': [acc.to_dict() for acc in accounts],
        'total_balance': sum(acc.balance for acc in accounts)
    }), 200


@payments_bp.route('/add-money', methods=['POST'])
@token_required
def add_money(current_user):
    """Add money to account (for demo/testing)"""
    data = request.get_json()
    db = get_db()
    Transaction, Account, User, Notification = get_models()
    
    amount = float(data.get('amount', 0))
    if amount <= 0:
        return jsonify({'error': 'Amount must be positive'}), 400
    
    account = Account.query.filter_by(user_id=current_user.id, is_primary=True).first()
    if not account:
        return jsonify({'error': 'No account found'}), 400
    
    balance_before = account.balance
    account.balance += amount
    
    # Create transaction record
    transaction = Transaction(
        id=str(uuid.uuid4()),
        transaction_id=generate_transaction_id(),
        receiver_id=current_user.id,
        receiver_account_id=account.id,
        transaction_type='CASH_IN',
        amount=amount,
        receiver_balance_before=balance_before,
        receiver_balance_after=account.balance,
        description=data.get('description', 'Added money to wallet'),
        category='Income',
        status='completed',
        completed_at=datetime.utcnow()
    )
    
    db.session.add(transaction)
    db.session.commit()
    
    # Send balance update
    emitter = get_notification_emitter()
    if emitter:
        emitter.emit_balance_update(account.id, current_user.id, {
            'previous_balance': balance_before,
            'current_balance': account.balance,
            'change': amount
        })
    
    return jsonify({
        'message': 'Money added successfully',
        'new_balance': account.balance,
        'transaction': transaction.to_dict()
    }), 200
