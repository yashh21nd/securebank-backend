"""
Authentication Routes
Handles user registration, login, and token management
"""
from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
from datetime import datetime, timedelta
from functools import wraps
import uuid

auth_bp = Blueprint('auth', __name__)


def get_db():
    from app import db
    return db


def get_user_model():
    from app.models import User
    return User


def get_account_model():
    from app.models import Account
    return Account


def generate_account_number():
    """Generate a unique account number"""
    import random
    return ''.join([str(random.randint(0, 9)) for _ in range(12)])


def generate_upi_id(username):
    """Generate a UPI ID from username"""
    return f"{username}@securebank"


def token_required(f):
    """Decorator for routes that require authentication"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(" ")[1]
            except IndexError:
                return jsonify({'error': 'Invalid token format'}), 401
        
        if not token:
            return jsonify({'error': 'Token is missing'}), 401
        
        try:
            from flask import current_app
            data = jwt.decode(token, current_app.config['JWT_SECRET_KEY'], algorithms=['HS256'])
            User = get_user_model()
            current_user = User.query.filter_by(id=data['user_id']).first()
            
            if not current_user:
                return jsonify({'error': 'User not found'}), 401
            
            if not current_user.is_active:
                return jsonify({'error': 'User account is deactivated'}), 401
                
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401
        
        return f(current_user, *args, **kwargs)
    
    return decorated


@auth_bp.route('/register', methods=['POST'])
def register():
    """Register a new user"""
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['username', 'email', 'password']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'{field} is required'}), 400
    
    User = get_user_model()
    Account = get_account_model()
    db = get_db()
    
    # Check if user already exists
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'error': 'Username already exists'}), 400
    
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email already registered'}), 400
    
    if data.get('phone') and User.query.filter_by(phone=data['phone']).first():
        return jsonify({'error': 'Phone number already registered'}), 400
    
    try:
        # Create user
        user = User(
            id=str(uuid.uuid4()),
            username=data['username'],
            email=data['email'],
            password_hash=generate_password_hash(data['password']),
            phone=data.get('phone'),
            full_name=data.get('full_name'),
            upi_id=generate_upi_id(data['username'])
        )
        
        db.session.add(user)
        db.session.flush()  # Get user ID before commit
        
        # Create default account
        account = Account(
            id=str(uuid.uuid4()),
            user_id=user.id,
            account_number=generate_account_number(),
            account_type='savings',
            balance=10000.0,  # Initial balance for demo
            is_primary=True
        )
        
        db.session.add(account)
        db.session.commit()
        
        return jsonify({
            'message': 'User registered successfully',
            'user': user.to_dict(),
            'account': account.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/login', methods=['POST'])
def login():
    """User login"""
    data = request.get_json()
    
    if not data.get('username') and not data.get('email'):
        return jsonify({'error': 'Username or email is required'}), 400
    
    if not data.get('password'):
        return jsonify({'error': 'Password is required'}), 400
    
    User = get_user_model()
    
    # Find user by username or email
    user = None
    if data.get('username'):
        user = User.query.filter_by(username=data['username']).first()
    elif data.get('email'):
        user = User.query.filter_by(email=data['email']).first()
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    if not check_password_hash(user.password_hash, data['password']):
        return jsonify({'error': 'Invalid password'}), 401
    
    if not user.is_active:
        return jsonify({'error': 'Account is deactivated'}), 401
    
    # Generate JWT token
    from flask import current_app
    token = jwt.encode({
        'user_id': user.id,
        'username': user.username,
        'exp': datetime.utcnow() + timedelta(hours=24)
    }, current_app.config['JWT_SECRET_KEY'], algorithm='HS256')
    
    # Get user's accounts
    accounts = [acc.to_dict() for acc in user.accounts]
    
    return jsonify({
        'message': 'Login successful',
        'token': token,
        'user': user.to_dict(),
        'accounts': accounts
    }), 200


@auth_bp.route('/logout', methods=['POST'])
@token_required
def logout(current_user):
    """User logout (client should discard token)"""
    return jsonify({'message': 'Logged out successfully'}), 200


@auth_bp.route('/profile', methods=['GET'])
@token_required
def get_profile(current_user):
    """Get current user profile"""
    accounts = [acc.to_dict() for acc in current_user.accounts]
    return jsonify({
        'user': current_user.to_dict(),
        'accounts': accounts
    }), 200


@auth_bp.route('/profile', methods=['PUT'])
@token_required
def update_profile(current_user):
    """Update user profile"""
    data = request.get_json()
    db = get_db()
    
    # Update allowed fields
    if data.get('full_name'):
        current_user.full_name = data['full_name']
    if data.get('phone'):
        current_user.phone = data['phone']
    
    try:
        db.session.commit()
        return jsonify({
            'message': 'Profile updated successfully',
            'user': current_user.to_dict()
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/change-password', methods=['POST'])
@token_required
def change_password(current_user):
    """Change user password"""
    data = request.get_json()
    db = get_db()
    
    if not data.get('current_password'):
        return jsonify({'error': 'Current password is required'}), 400
    
    if not data.get('new_password'):
        return jsonify({'error': 'New password is required'}), 400
    
    if not check_password_hash(current_user.password_hash, data['current_password']):
        return jsonify({'error': 'Current password is incorrect'}), 401
    
    current_user.password_hash = generate_password_hash(data['new_password'])
    
    try:
        db.session.commit()
        return jsonify({'message': 'Password changed successfully'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/verify-token', methods=['GET'])
@token_required
def verify_token(current_user):
    """Verify if token is valid"""
    return jsonify({
        'valid': True,
        'user_id': current_user.id,
        'username': current_user.username
    }), 200
