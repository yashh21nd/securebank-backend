"""
Speech Recognition Routes
Handles voice command processing for payments
"""
from flask import Blueprint, request, jsonify
from app.routes.auth import token_required
import base64

speech_bp = Blueprint('speech', __name__)


def get_db():
    from app import db
    return db


def get_models():
    from app.models import User
    return User


def get_speech_service():
    from app.services.speech_recognition import speech_service
    return speech_service


@speech_bp.route('/recognize', methods=['POST'])
@token_required
def recognize_speech(current_user):
    """
    Recognize speech from audio data
    
    Accepts:
    - audio_data: base64 encoded audio bytes
    - sample_rate: audio sample rate (default 16000)
    - sample_width: audio sample width in bytes (default 2)
    """
    data = request.get_json()
    speech_service = get_speech_service()
    
    audio_base64 = data.get('audio_data')
    if not audio_base64:
        return jsonify({'error': 'Audio data is required'}), 400
    
    try:
        # Decode base64 audio
        audio_bytes = base64.b64decode(audio_base64)
        
        # Get audio parameters
        sample_rate = data.get('sample_rate', 16000)
        sample_width = data.get('sample_width', 2)
        
        # Recognize speech
        result = speech_service.recognize_from_audio_data(
            audio_bytes, 
            sample_rate=sample_rate,
            sample_width=sample_width
        )
        
        # If payment command, resolve recipient
        if result.get('success') and result.get('parsed', {}).get('intent') == 'payment':
            result['parsed'] = _resolve_recipient(current_user, result['parsed'])
        
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'processing_error',
            'message': str(e)
        }), 500


@speech_bp.route('/parse-text', methods=['POST'])
@token_required
def parse_text_command(current_user):
    """
    Parse a text command (for testing or text-based input)
    
    Accepts:
    - text: command text
    """
    data = request.get_json()
    speech_service = get_speech_service()
    
    text = data.get('text', '').strip()
    if not text:
        return jsonify({'error': 'Text is required'}), 400
    
    # Parse the command
    result = speech_service.parse_text_command(text)
    
    # If payment command, resolve recipient
    if result.get('intent') == 'payment':
        result = _resolve_recipient(current_user, result)
    
    return jsonify({
        'success': True,
        'text': text,
        'parsed': result
    }), 200


def _resolve_recipient(current_user, parsed_command):
    """Resolve recipient name to user ID"""
    User = get_models()
    
    if parsed_command.get('intent') != 'payment':
        return parsed_command
    
    params = parsed_command.get('params', {})
    recipient = params.get('recipient', '')
    recipient_type = params.get('recipient_type', 'name')
    
    user = None
    
    if recipient_type == 'phone':
        user = User.query.filter_by(phone=recipient).first()
    elif recipient_type == 'upi_id':
        user = User.query.filter_by(upi_id=recipient).first()
    elif recipient_type == 'name':
        # Search by name or username
        user = User.query.filter(
            (User.username.ilike(f'%{recipient}%')) |
            (User.full_name.ilike(f'%{recipient}%'))
        ).filter(User.id != current_user.id).first()
    
    if user:
        params['resolved_user'] = {
            'id': user.id,
            'username': user.username,
            'full_name': user.full_name,
            'upi_id': user.upi_id
        }
        params['recipient_resolved'] = True
    else:
        params['recipient_resolved'] = False
        params['resolution_message'] = f'Could not find user "{recipient}"'
    
    parsed_command['params'] = params
    return parsed_command


@speech_bp.route('/execute-command', methods=['POST'])
@token_required
def execute_voice_command(current_user):
    """
    Execute a parsed voice command
    
    Accepts:
    - command: parsed command object from recognize or parse-text
    """
    data = request.get_json()
    
    command = data.get('command', {})
    intent = command.get('intent')
    params = command.get('params', {})
    
    if intent == 'payment':
        return _execute_payment(current_user, params)
    elif intent == 'balance':
        return _execute_balance_check(current_user)
    elif intent == 'transactions':
        return _execute_transactions(current_user)
    elif intent == 'request_money':
        return _execute_money_request(current_user, params)
    else:
        return jsonify({
            'success': False,
            'error': 'Unknown command',
            'message': 'Could not understand the command'
        }), 400


def _execute_payment(current_user, params):
    """Execute a payment command"""
    from app.routes.payments import send_money
    from flask import g
    
    if not params.get('recipient_resolved'):
        return jsonify({
            'success': False,
            'error': 'recipient_not_found',
            'message': params.get('resolution_message', 'Could not find recipient')
        }), 400
    
    resolved_user = params.get('resolved_user', {})
    amount = params.get('amount', 0)
    
    # Create payment request
    from flask import Request
    import json
    
    # Instead of making internal request, return confirmation needed
    return jsonify({
        'success': True,
        'action': 'confirm_payment',
        'confirmation_required': True,
        'payment_details': {
            'receiver_id': resolved_user.get('id'),
            'receiver_name': resolved_user.get('full_name') or resolved_user.get('username'),
            'receiver_upi': resolved_user.get('upi_id'),
            'amount': amount
        },
        'message': f"Send ₹{amount} to {resolved_user.get('full_name') or resolved_user.get('username')}?"
    }), 200


def _execute_balance_check(current_user):
    """Execute balance check command"""
    from app.models import Account
    
    accounts = Account.query.filter_by(user_id=current_user.id).all()
    total_balance = sum(acc.balance for acc in accounts)
    
    return jsonify({
        'success': True,
        'action': 'balance_check',
        'balance': {
            'total': total_balance,
            'accounts': [acc.to_dict() for acc in accounts]
        },
        'message': f"Your balance is ₹{total_balance:.2f}"
    }), 200


def _execute_transactions(current_user):
    """Execute transactions check command"""
    from app.models import Transaction, User
    
    transactions = Transaction.query.filter(
        (Transaction.sender_id == current_user.id) | (Transaction.receiver_id == current_user.id)
    ).order_by(Transaction.created_at.desc()).limit(5).all()
    
    result = []
    for tx in transactions:
        tx_dict = tx.to_dict()
        if tx.sender_id == current_user.id:
            tx_dict['direction'] = 'sent'
            if tx.receiver_id:
                receiver = User.query.get(tx.receiver_id)
                tx_dict['party_name'] = receiver.full_name or receiver.username if receiver else 'Unknown'
        else:
            tx_dict['direction'] = 'received'
            if tx.sender_id:
                sender = User.query.get(tx.sender_id)
                tx_dict['party_name'] = sender.full_name or sender.username if sender else 'Unknown'
        result.append(tx_dict)
    
    return jsonify({
        'success': True,
        'action': 'transactions',
        'transactions': result,
        'message': f"Here are your last {len(result)} transactions"
    }), 200


def _execute_money_request(current_user, params):
    """Execute money request command"""
    User = get_models()
    
    from_user_name = params.get('from_user', '')
    amount = params.get('amount', 0)
    
    # Find user
    user = User.query.filter(
        (User.username.ilike(f'%{from_user_name}%')) |
        (User.full_name.ilike(f'%{from_user_name}%'))
    ).filter(User.id != current_user.id).first()
    
    if not user:
        return jsonify({
            'success': False,
            'error': 'user_not_found',
            'message': f'Could not find user "{from_user_name}"'
        }), 400
    
    return jsonify({
        'success': True,
        'action': 'confirm_request',
        'confirmation_required': True,
        'request_details': {
            'from_user_id': user.id,
            'from_user_name': user.full_name or user.username,
            'amount': amount
        },
        'message': f"Request ₹{amount} from {user.full_name or user.username}?"
    }), 200


@speech_bp.route('/supported-commands', methods=['GET'])
@token_required
def get_supported_commands(current_user):
    """Get list of supported voice commands"""
    speech_service = get_speech_service()
    
    return jsonify({
        'commands': speech_service.get_supported_commands()
    }), 200
