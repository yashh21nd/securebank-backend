"""
User Routes
Handles user search, contacts, and user-related operations
"""
from flask import Blueprint, request, jsonify
from app.routes.auth import token_required

users_bp = Blueprint('users', __name__)


def get_db():
    from app import db
    return db


def get_user_model():
    from app.models import User
    return User


@users_bp.route('/search', methods=['GET'])
@token_required
def search_users(current_user):
    """Search for users by username, phone, or UPI ID"""
    query = request.args.get('q', '').strip()
    
    if len(query) < 2:
        return jsonify({'error': 'Search query must be at least 2 characters'}), 400
    
    User = get_user_model()
    
    # Search by username, phone, or UPI ID
    users = User.query.filter(
        (User.username.ilike(f'%{query}%')) |
        (User.phone.ilike(f'%{query}%')) |
        (User.upi_id.ilike(f'%{query}%')) |
        (User.full_name.ilike(f'%{query}%'))
    ).filter(
        User.id != current_user.id,
        User.is_active == True
    ).limit(10).all()
    
    results = [{
        'id': user.id,
        'username': user.username,
        'full_name': user.full_name,
        'upi_id': user.upi_id,
        'phone': user.phone[-4:] if user.phone else None  # Show only last 4 digits
    } for user in users]
    
    return jsonify({'users': results}), 200


@users_bp.route('/find-by-upi', methods=['GET'])
@token_required
def find_by_upi(current_user):
    """Find user by UPI ID"""
    upi_id = request.args.get('upi_id', '').strip()
    
    if not upi_id:
        return jsonify({'error': 'UPI ID is required'}), 400
    
    User = get_user_model()
    user = User.query.filter_by(upi_id=upi_id, is_active=True).first()
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    return jsonify({
        'user': {
            'id': user.id,
            'username': user.username,
            'full_name': user.full_name,
            'upi_id': user.upi_id
        }
    }), 200


@users_bp.route('/find-by-phone', methods=['GET'])
@token_required
def find_by_phone(current_user):
    """Find user by phone number"""
    phone = request.args.get('phone', '').strip()
    
    if not phone:
        return jsonify({'error': 'Phone number is required'}), 400
    
    User = get_user_model()
    user = User.query.filter_by(phone=phone, is_active=True).first()
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    return jsonify({
        'user': {
            'id': user.id,
            'username': user.username,
            'full_name': user.full_name,
            'upi_id': user.upi_id
        }
    }), 200


@users_bp.route('/<user_id>', methods=['GET'])
@token_required
def get_user(current_user, user_id):
    """Get user details by ID"""
    User = get_user_model()
    user = User.query.filter_by(id=user_id, is_active=True).first()
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # Return limited info for other users
    return jsonify({
        'user': {
            'id': user.id,
            'username': user.username,
            'full_name': user.full_name,
            'upi_id': user.upi_id
        }
    }), 200


@users_bp.route('/contacts', methods=['GET'])
@token_required
def get_contacts(current_user):
    """Get recent transaction contacts"""
    from app.models import Transaction
    
    # Get unique users from recent transactions
    sent_to = Transaction.query.filter_by(sender_id=current_user.id).with_entities(
        Transaction.receiver_id
    ).distinct().limit(20).all()
    
    received_from = Transaction.query.filter_by(receiver_id=current_user.id).with_entities(
        Transaction.sender_id
    ).distinct().limit(20).all()
    
    contact_ids = set()
    for tx in sent_to:
        if tx.receiver_id:
            contact_ids.add(tx.receiver_id)
    for tx in received_from:
        if tx.sender_id:
            contact_ids.add(tx.sender_id)
    
    # Remove current user
    contact_ids.discard(current_user.id)
    
    User = get_user_model()
    contacts = User.query.filter(User.id.in_(contact_ids), User.is_active == True).all()
    
    return jsonify({
        'contacts': [{
            'id': user.id,
            'username': user.username,
            'full_name': user.full_name,
            'upi_id': user.upi_id
        } for user in contacts]
    }), 200
