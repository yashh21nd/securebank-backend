"""
PIN Management Routes
Handles security PIN for payments
"""
from flask import Blueprint, request, jsonify
from app.routes.auth import token_required
from datetime import datetime, timedelta
import bcrypt

pin_bp = Blueprint('pin', __name__)


def get_db():
    from app import db
    return db


def get_user_model():
    from app.models import User
    return User


def hash_pin(pin):
    """Hash a PIN using bcrypt"""
    return bcrypt.hashpw(pin.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_pin(pin, pin_hash):
    """Verify a PIN against its hash"""
    return bcrypt.checkpw(pin.encode('utf-8'), pin_hash.encode('utf-8'))


@pin_bp.route('/setup', methods=['POST'])
@token_required
def setup_pin(current_user):
    """Set up a new security PIN"""
    data = request.get_json()
    db = get_db()
    
    pin = data.get('pin')
    confirm_pin = data.get('confirm_pin')
    
    if not pin or not confirm_pin:
        return jsonify({'error': 'PIN and confirmation required'}), 400
    
    if len(pin) != 4 or not pin.isdigit():
        return jsonify({'error': 'PIN must be exactly 4 digits'}), 400
    
    if pin != confirm_pin:
        return jsonify({'error': 'PINs do not match'}), 400
    
    if current_user.security_pin_hash:
        return jsonify({'error': 'PIN already exists. Use change PIN endpoint'}), 400
    
    current_user.security_pin_hash = hash_pin(pin)
    current_user.pin_created_at = datetime.utcnow()
    current_user.pin_attempts = 0
    db.session.commit()
    
    return jsonify({
        'message': 'Security PIN set successfully',
        'has_pin': True
    }), 200


@pin_bp.route('/change', methods=['POST'])
@token_required
def change_pin(current_user):
    """Change existing security PIN"""
    data = request.get_json()
    db = get_db()
    
    current_pin = data.get('current_pin')
    new_pin = data.get('new_pin')
    confirm_pin = data.get('confirm_pin')
    
    if not all([current_pin, new_pin, confirm_pin]):
        return jsonify({'error': 'Current PIN, new PIN, and confirmation required'}), 400
    
    if not current_user.security_pin_hash:
        return jsonify({'error': 'No PIN set. Use setup endpoint'}), 400
    
    # Check if locked
    if current_user.pin_locked_until and current_user.pin_locked_until > datetime.utcnow():
        remaining = (current_user.pin_locked_until - datetime.utcnow()).seconds
        return jsonify({'error': f'PIN locked. Try again in {remaining} seconds'}), 403
    
    # Verify current PIN
    if not verify_pin(current_pin, current_user.security_pin_hash):
        current_user.pin_attempts += 1
        if current_user.pin_attempts >= 3:
            current_user.pin_locked_until = datetime.utcnow() + timedelta(minutes=15)
            db.session.commit()
            return jsonify({'error': 'Too many attempts. PIN locked for 15 minutes'}), 403
        db.session.commit()
        return jsonify({'error': 'Current PIN is incorrect'}), 400
    
    if len(new_pin) != 4 or not new_pin.isdigit():
        return jsonify({'error': 'New PIN must be exactly 4 digits'}), 400
    
    if new_pin != confirm_pin:
        return jsonify({'error': 'New PINs do not match'}), 400
    
    current_user.security_pin_hash = hash_pin(new_pin)
    current_user.pin_created_at = datetime.utcnow()
    current_user.pin_attempts = 0
    current_user.pin_locked_until = None
    db.session.commit()
    
    return jsonify({'message': 'PIN changed successfully'}), 200


@pin_bp.route('/verify', methods=['POST'])
@token_required
def verify_user_pin(current_user):
    """Verify PIN for payment authorization"""
    data = request.get_json()
    db = get_db()
    
    pin = data.get('pin')
    
    if not pin:
        return jsonify({'error': 'PIN required'}), 400
    
    if not current_user.security_pin_hash:
        return jsonify({'error': 'No PIN set', 'has_pin': False}), 400
    
    # Check if locked
    if current_user.pin_locked_until and current_user.pin_locked_until > datetime.utcnow():
        remaining = (current_user.pin_locked_until - datetime.utcnow()).seconds
        return jsonify({'error': f'PIN locked. Try again in {remaining} seconds', 'locked': True}), 403
    
    if verify_pin(pin, current_user.security_pin_hash):
        current_user.pin_attempts = 0
        db.session.commit()
        return jsonify({'verified': True, 'message': 'PIN verified'}), 200
    else:
        current_user.pin_attempts += 1
        if current_user.pin_attempts >= 3:
            current_user.pin_locked_until = datetime.utcnow() + timedelta(minutes=15)
            db.session.commit()
            return jsonify({'error': 'Too many attempts. PIN locked for 15 minutes', 'locked': True}), 403
        db.session.commit()
        remaining_attempts = 3 - current_user.pin_attempts
        return jsonify({'error': f'Incorrect PIN. {remaining_attempts} attempts remaining', 'verified': False}), 400


@pin_bp.route('/status', methods=['GET'])
@token_required
def pin_status(current_user):
    """Get PIN status for current user"""
    has_pin = current_user.security_pin_hash is not None
    is_locked = current_user.pin_locked_until and current_user.pin_locked_until > datetime.utcnow()
    
    return jsonify({
        'has_pin': has_pin,
        'is_locked': is_locked,
        'pin_created_at': current_user.pin_created_at.isoformat() if current_user.pin_created_at else None,
        'attempts_remaining': max(0, 3 - current_user.pin_attempts) if has_pin else None
    }), 200


@pin_bp.route('/reset', methods=['POST'])
@token_required
def reset_pin(current_user):
    """Reset PIN (requires password verification)"""
    data = request.get_json()
    db = get_db()
    
    password = data.get('password')
    new_pin = data.get('new_pin')
    confirm_pin = data.get('confirm_pin')
    
    if not all([password, new_pin, confirm_pin]):
        return jsonify({'error': 'Password, new PIN, and confirmation required'}), 400
    
    # Verify password
    if not bcrypt.checkpw(password.encode('utf-8'), current_user.password_hash.encode('utf-8')):
        return jsonify({'error': 'Invalid password'}), 400
    
    if len(new_pin) != 4 or not new_pin.isdigit():
        return jsonify({'error': 'PIN must be exactly 4 digits'}), 400
    
    if new_pin != confirm_pin:
        return jsonify({'error': 'PINs do not match'}), 400
    
    current_user.security_pin_hash = hash_pin(new_pin)
    current_user.pin_created_at = datetime.utcnow()
    current_user.pin_attempts = 0
    current_user.pin_locked_until = None
    db.session.commit()
    
    return jsonify({'message': 'PIN reset successfully'}), 200


# Demo mode endpoints (no auth required)
@pin_bp.route('/demo/status', methods=['GET'])
def demo_pin_status():
    """Demo mode PIN status"""
    return jsonify({
        'has_pin': True,
        'is_locked': False,
        'attempts_remaining': 3
    }), 200


@pin_bp.route('/demo/verify', methods=['POST'])
def demo_verify_pin():
    """Demo mode PIN verification"""
    data = request.get_json()
    pin = data.get('pin', '')
    
    # Demo PIN is 1234
    if pin == '1234':
        return jsonify({'verified': True, 'message': 'PIN verified'}), 200
    else:
        return jsonify({'error': 'Incorrect PIN. Demo PIN is 1234', 'verified': False}), 400


@pin_bp.route('/demo/setup', methods=['POST'])
def demo_setup_pin():
    """Demo mode PIN setup"""
    return jsonify({
        'message': 'Security PIN set successfully (Demo mode: PIN is 1234)',
        'has_pin': True
    }), 200
