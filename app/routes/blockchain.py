"""
Blockchain Routes
Handles blockchain QR code generation and verification
"""
from flask import Blueprint, request, jsonify, send_file
from datetime import datetime, timedelta
import uuid
import io
import base64
from app.routes.auth import token_required

blockchain_bp = Blueprint('blockchain', __name__)


def get_db():
    from app import db
    return db


def get_models():
    from app.models import QRPayment, User, Transaction, Account
    return QRPayment, User, Transaction, Account


def get_services():
    from app.services.blockchain import blockchain, qr_generator
    return blockchain, qr_generator


@blockchain_bp.route('/generate-qr', methods=['POST'])
@token_required
def generate_payment_qr(current_user):
    """
    Generate a secure blockchain-based QR code for receiving payment
    """
    data = request.get_json()
    db = get_db()
    QRPayment, User, Transaction, Account = get_models()
    blockchain, qr_generator = get_services()
    
    amount = data.get('amount')  # Can be None for dynamic amount
    description = data.get('description', '')
    expires_in_minutes = data.get('expires_in_minutes', 5)
    is_single_use = data.get('is_single_use', True)
    
    # Create blockchain hash for the payment
    payment_data = {
        'creator_id': current_user.id,
        'creator_upi': current_user.upi_id,
        'creator_name': current_user.full_name or current_user.username,
        'amount': amount,
        'description': description,
        'timestamp': datetime.utcnow().isoformat()
    }
    
    blockchain_hash = blockchain.add_transaction(payment_data)
    
    # Generate secure QR code
    qr_result = qr_generator.generate_payment_qr({
        'receiver_id': current_user.id,
        'receiver_upi': current_user.upi_id,
        'amount': amount,
        'description': description,
        'expires_in_minutes': expires_in_minutes
    }, blockchain_hash)
    
    # Save QR payment record
    qr_payment = QRPayment(
        id=qr_result['payment_id'],
        creator_id=current_user.id,
        amount=amount,
        description=description,
        qr_code_hash=qr_result['qr_code_hash'],
        qr_code_data=qr_result['qr_code_data'],
        blockchain_signature=qr_result['signature'],
        nonce=qr_result['nonce'],
        is_single_use=is_single_use,
        expires_at=datetime.fromisoformat(qr_result['expires_at'])
    )
    
    db.session.add(qr_payment)
    db.session.commit()
    
    return jsonify({
        'payment_id': qr_result['payment_id'],
        'qr_code_image': qr_result['qr_code_image'],
        'qr_code_hash': qr_result['qr_code_hash'],
        'expires_at': qr_result['expires_at'],
        'blockchain_hash': blockchain_hash,
        'amount': amount,
        'description': description
    }), 200


@blockchain_bp.route('/generate-upi-qr', methods=['POST'])
@token_required
def generate_upi_qr(current_user):
    """
    Generate a UPI-compatible QR code
    """
    data = request.get_json()
    blockchain, qr_generator = get_services()
    
    amount = data.get('amount')
    note = data.get('note', '')
    
    result = qr_generator.generate_upi_qr(
        upi_id=current_user.upi_id,
        name=current_user.full_name or current_user.username,
        amount=amount,
        note=note
    )
    
    return jsonify({
        'qr_code_image': result['qr_code_image'],
        'upi_url': result['upi_url'],
        'transaction_ref': result['transaction_ref']
    }), 200


@blockchain_bp.route('/verify-qr', methods=['POST'])
@token_required
def verify_qr_code(current_user):
    """
    Verify a scanned QR code
    """
    data = request.get_json()
    db = get_db()
    QRPayment, User, Transaction, Account = get_models()
    blockchain, qr_generator = get_services()
    
    qr_data = data.get('qr_data')
    if not qr_data:
        return jsonify({'error': 'QR data is required'}), 400
    
    # Verify the QR code
    verification = qr_generator.verify_qr_payment(qr_data)
    
    if not verification['valid']:
        return jsonify({
            'valid': False,
            'error': verification.get('error', 'Invalid QR code')
        }), 400
    
    payment_data = verification['payment_data']
    
    # Check if QR payment exists and is valid
    qr_payment = QRPayment.query.get(payment_data['payment_id'])
    
    if not qr_payment:
        return jsonify({'valid': False, 'error': 'QR payment not found'}), 404
    
    if qr_payment.status == 'used':
        return jsonify({'valid': False, 'error': 'QR code has already been used'}), 400
    
    if qr_payment.status == 'expired':
        return jsonify({'valid': False, 'error': 'QR code has expired'}), 400
    
    if datetime.utcnow() > qr_payment.expires_at:
        qr_payment.status = 'expired'
        db.session.commit()
        return jsonify({'valid': False, 'error': 'QR code has expired'}), 400
    
    # Get receiver info
    receiver = User.query.get(payment_data['receiver_id'])
    
    return jsonify({
        'valid': True,
        'payment_id': payment_data['payment_id'],
        'receiver': {
            'id': receiver.id,
            'name': receiver.full_name or receiver.username,
            'upi_id': receiver.upi_id
        } if receiver else None,
        'amount': payment_data.get('amount'),
        'description': payment_data.get('description', ''),
        'expires_at': payment_data.get('expires_at')
    }), 200


@blockchain_bp.route('/pay-via-qr', methods=['POST'])
@token_required
def pay_via_qr(current_user):
    """
    Complete payment using a scanned QR code
    """
    data = request.get_json()
    db = get_db()
    QRPayment, User, Transaction, Account = get_models()
    blockchain, qr_generator = get_services()
    
    payment_id = data.get('payment_id')
    amount = data.get('amount')  # Override amount if QR doesn't specify
    
    if not payment_id:
        return jsonify({'error': 'Payment ID is required'}), 400
    
    qr_payment = QRPayment.query.get(payment_id)
    
    if not qr_payment:
        return jsonify({'error': 'QR payment not found'}), 404
    
    if qr_payment.status != 'active':
        return jsonify({'error': f'QR code status: {qr_payment.status}'}), 400
    
    if datetime.utcnow() > qr_payment.expires_at:
        qr_payment.status = 'expired'
        db.session.commit()
        return jsonify({'error': 'QR code has expired'}), 400
    
    # Determine final amount
    final_amount = qr_payment.amount or amount
    if not final_amount:
        return jsonify({'error': 'Amount is required'}), 400
    
    final_amount = float(final_amount)
    
    # Cannot pay yourself
    if qr_payment.creator_id == current_user.id:
        return jsonify({'error': 'Cannot pay yourself'}), 400
    
    # Get accounts
    sender_account = Account.query.filter_by(user_id=current_user.id, is_primary=True).first()
    receiver_account = Account.query.filter_by(user_id=qr_payment.creator_id, is_primary=True).first()
    receiver = User.query.get(qr_payment.creator_id)
    
    if not sender_account:
        return jsonify({'error': 'No account found'}), 400
    
    if sender_account.balance < final_amount:
        return jsonify({'error': 'Insufficient balance'}), 400
    
    # Import payment processing
    from app.routes.payments import generate_transaction_id
    from app.services.fraud_detection import fraud_service
    from app.websocket import get_notification_emitter
    
    # Fraud check
    fraud_check = fraud_service.predict_fraud({
        'type': 'PAYMENT',
        'amount': final_amount,
        'oldbalanceOrg': sender_account.balance,
        'newbalanceOrig': sender_account.balance - final_amount,
        'oldbalanceDest': receiver_account.balance if receiver_account else 0,
        'newbalanceDest': (receiver_account.balance if receiver_account else 0) + final_amount,
        'step': datetime.utcnow().hour
    })
    
    if fraud_check.get('should_block'):
        return jsonify({
            'error': 'Transaction blocked due to suspicious activity',
            'fraud_alert': {
                'risk_level': fraud_check['risk_level'],
                'risk_factors': fraud_check['risk_factors']
            }
        }), 403
    
    try:
        # Process payment
        sender_balance_before = sender_account.balance
        receiver_balance_before = receiver_account.balance if receiver_account else 0
        
        sender_account.balance -= final_amount
        if receiver_account:
            receiver_account.balance += final_amount
        
        # Add to blockchain
        tx_hash = blockchain.add_transaction({
            'sender': current_user.id,
            'receiver': qr_payment.creator_id,
            'amount': final_amount,
            'qr_payment_id': payment_id,
            'timestamp': datetime.utcnow().isoformat()
        })
        
        # Create transaction
        transaction = Transaction(
            id=str(uuid.uuid4()),
            transaction_id=generate_transaction_id(),
            sender_id=current_user.id,
            receiver_id=qr_payment.creator_id,
            sender_account_id=sender_account.id,
            receiver_account_id=receiver_account.id if receiver_account else None,
            transaction_type='PAYMENT',
            amount=final_amount,
            sender_balance_before=sender_balance_before,
            sender_balance_after=sender_account.balance,
            receiver_balance_before=receiver_balance_before,
            receiver_balance_after=receiver_account.balance if receiver_account else receiver_balance_before + final_amount,
            description=qr_payment.description or 'QR Payment',
            category='Payment',
            status='completed',
            fraud_score=fraud_check['fraud_probability'],
            blockchain_hash=tx_hash,
            qr_payment_id=payment_id,
            completed_at=datetime.utcnow()
        )
        
        db.session.add(transaction)
        
        # Update QR payment status
        if qr_payment.is_single_use:
            qr_payment.status = 'used'
            qr_payment.used_at = datetime.utcnow()
            qr_payment.used_by = current_user.id
        
        db.session.commit()
        
        # Send notifications
        emitter = get_notification_emitter()
        if emitter:
            emitter.emit_payment_received(qr_payment.creator_id, {
                'transaction_id': transaction.transaction_id,
                'amount': final_amount,
                'sender_id': current_user.id,
                'sender_name': current_user.full_name or current_user.username
            })
            
            emitter.emit_payment_sent(current_user.id, {
                'transaction_id': transaction.transaction_id,
                'amount': final_amount,
                'receiver_id': qr_payment.creator_id,
                'receiver_name': receiver.full_name or receiver.username if receiver else 'Unknown',
                'new_balance': sender_account.balance
            })
        
        return jsonify({
            'message': 'Payment successful',
            'transaction': transaction.to_dict(),
            'new_balance': sender_account.balance
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@blockchain_bp.route('/chain', methods=['GET'])
@token_required
def get_blockchain(current_user):
    """Get the blockchain (for verification purposes)"""
    blockchain, _ = get_services()
    
    return jsonify({
        'chain': blockchain.get_chain(),
        'length': len(blockchain.chain),
        'is_valid': blockchain.is_chain_valid()
    }), 200


@blockchain_bp.route('/verify-transaction/<tx_hash>', methods=['GET'])
@token_required
def verify_blockchain_transaction(current_user, tx_hash):
    """Verify a transaction on the blockchain"""
    blockchain, _ = get_services()
    
    verification = blockchain.verify_transaction(tx_hash)
    
    return jsonify(verification), 200


@blockchain_bp.route('/mine', methods=['POST'])
@token_required
def mine_block(current_user):
    """Mine pending transactions into a new block"""
    blockchain, _ = get_services()
    
    new_block = blockchain.mine_block()
    
    if not new_block:
        return jsonify({'message': 'No transactions to mine'}), 200
    
    return jsonify({
        'message': 'Block mined successfully',
        'block': new_block.to_dict()
    }), 200


@blockchain_bp.route('/my-qr-payments', methods=['GET'])
@token_required
def get_my_qr_payments(current_user):
    """Get user's generated QR payments"""
    QRPayment, User, Transaction, Account = get_models()
    
    qr_payments = QRPayment.query.filter_by(creator_id=current_user.id).order_by(
        QRPayment.created_at.desc()
    ).limit(20).all()
    
    return jsonify({
        'qr_payments': [qr.to_dict() for qr in qr_payments]
    }), 200
