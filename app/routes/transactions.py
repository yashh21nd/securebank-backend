"""
Transaction Routes
Handles viewing and managing transactions
"""
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
from app.routes.auth import token_required

transactions_bp = Blueprint('transactions', __name__)


def get_db():
    from app import db
    return db


def get_models():
    from app.models import Transaction, Account, User
    return Transaction, Account, User


@transactions_bp.route('/', methods=['GET'])
@token_required
def get_transactions(current_user):
    """Get user's transactions with pagination and filters"""
    Transaction, Account, User = get_models()
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    per_page = min(per_page, 100)  # Max 100 per page
    
    # Filters
    transaction_type = request.args.get('type')
    status = request.args.get('status')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    # Build query
    query = Transaction.query.filter(
        (Transaction.sender_id == current_user.id) |
        (Transaction.receiver_id == current_user.id)
    )
    
    if transaction_type:
        query = query.filter(Transaction.transaction_type == transaction_type)
    
    if status:
        query = query.filter(Transaction.status == status)
    
    if start_date:
        query = query.filter(Transaction.created_at >= datetime.fromisoformat(start_date))
    
    if end_date:
        query = query.filter(Transaction.created_at <= datetime.fromisoformat(end_date))
    
    # Order by date descending
    query = query.order_by(Transaction.created_at.desc())
    
    # Paginate
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    transactions = []
    for tx in pagination.items:
        tx_dict = tx.to_dict()
        
        # Add sender/receiver names
        if tx.sender_id:
            sender = User.query.get(tx.sender_id)
            tx_dict['sender_name'] = sender.full_name or sender.username if sender else 'Unknown'
        
        if tx.receiver_id:
            receiver = User.query.get(tx.receiver_id)
            tx_dict['receiver_name'] = receiver.full_name or receiver.username if receiver else 'Unknown'
        
        # Mark as credit or debit for current user
        if tx.sender_id == current_user.id:
            tx_dict['direction'] = 'debit'
            tx_dict['display_amount'] = -tx.amount
        else:
            tx_dict['direction'] = 'credit'
            tx_dict['display_amount'] = tx.amount
        
        transactions.append(tx_dict)
    
    return jsonify({
        'transactions': transactions,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': pagination.total,
            'pages': pagination.pages,
            'has_next': pagination.has_next,
            'has_prev': pagination.has_prev
        }
    }), 200


@transactions_bp.route('/<transaction_id>', methods=['GET'])
@token_required
def get_transaction(current_user, transaction_id):
    """Get a specific transaction"""
    Transaction, Account, User = get_models()
    
    tx = Transaction.query.filter(
        Transaction.id == transaction_id,
        (Transaction.sender_id == current_user.id) | (Transaction.receiver_id == current_user.id)
    ).first()
    
    if not tx:
        return jsonify({'error': 'Transaction not found'}), 404
    
    tx_dict = tx.to_dict()
    
    # Add sender/receiver details
    if tx.sender_id:
        sender = User.query.get(tx.sender_id)
        tx_dict['sender'] = {
            'id': sender.id,
            'username': sender.username,
            'full_name': sender.full_name,
            'upi_id': sender.upi_id
        } if sender else None
    
    if tx.receiver_id:
        receiver = User.query.get(tx.receiver_id)
        tx_dict['receiver'] = {
            'id': receiver.id,
            'username': receiver.username,
            'full_name': receiver.full_name,
            'upi_id': receiver.upi_id
        } if receiver else None
    
    return jsonify({'transaction': tx_dict}), 200


@transactions_bp.route('/summary', methods=['GET'])
@token_required
def get_transaction_summary(current_user):
    """Get transaction summary/statistics"""
    Transaction, Account, User = get_models()
    from sqlalchemy import func
    
    # Time period
    period = request.args.get('period', 'month')  # day, week, month, year
    
    if period == 'day':
        start_date = datetime.utcnow() - timedelta(days=1)
    elif period == 'week':
        start_date = datetime.utcnow() - timedelta(weeks=1)
    elif period == 'month':
        start_date = datetime.utcnow() - timedelta(days=30)
    elif period == 'year':
        start_date = datetime.utcnow() - timedelta(days=365)
    else:
        start_date = datetime.utcnow() - timedelta(days=30)
    
    # Total sent
    sent_result = Transaction.query.filter(
        Transaction.sender_id == current_user.id,
        Transaction.status == 'completed',
        Transaction.created_at >= start_date
    ).with_entities(
        func.sum(Transaction.amount).label('total'),
        func.count(Transaction.id).label('count')
    ).first()
    
    # Total received
    received_result = Transaction.query.filter(
        Transaction.receiver_id == current_user.id,
        Transaction.status == 'completed',
        Transaction.created_at >= start_date
    ).with_entities(
        func.sum(Transaction.amount).label('total'),
        func.count(Transaction.id).label('count')
    ).first()
    
    # Category breakdown
    category_breakdown = Transaction.query.filter(
        Transaction.sender_id == current_user.id,
        Transaction.status == 'completed',
        Transaction.created_at >= start_date
    ).with_entities(
        Transaction.category,
        func.sum(Transaction.amount).label('total'),
        func.count(Transaction.id).label('count')
    ).group_by(Transaction.category).all()
    
    # Flagged transactions count
    flagged_count = Transaction.query.filter(
        (Transaction.sender_id == current_user.id) | (Transaction.receiver_id == current_user.id),
        Transaction.is_flagged == True,
        Transaction.created_at >= start_date
    ).count()
    
    return jsonify({
        'period': period,
        'summary': {
            'total_sent': sent_result.total or 0,
            'sent_count': sent_result.count or 0,
            'total_received': received_result.total or 0,
            'received_count': received_result.count or 0,
            'net_flow': (received_result.total or 0) - (sent_result.total or 0),
            'flagged_transactions': flagged_count
        },
        'category_breakdown': [{
            'category': cat[0] or 'Uncategorized',
            'total': cat[1] or 0,
            'count': cat[2] or 0
        } for cat in category_breakdown]
    }), 200


@transactions_bp.route('/recent', methods=['GET'])
@token_required
def get_recent_transactions(current_user):
    """Get recent transactions (last 10)"""
    Transaction, Account, User = get_models()
    
    transactions = Transaction.query.filter(
        (Transaction.sender_id == current_user.id) | (Transaction.receiver_id == current_user.id)
    ).order_by(Transaction.created_at.desc()).limit(10).all()
    
    result = []
    for tx in transactions:
        tx_dict = tx.to_dict()
        
        if tx.sender_id == current_user.id:
            tx_dict['direction'] = 'debit'
            tx_dict['display_amount'] = -tx.amount
            if tx.receiver_id:
                receiver = User.query.get(tx.receiver_id)
                tx_dict['party_name'] = receiver.full_name or receiver.username if receiver else 'Unknown'
        else:
            tx_dict['direction'] = 'credit'
            tx_dict['display_amount'] = tx.amount
            if tx.sender_id:
                sender = User.query.get(tx.sender_id)
                tx_dict['party_name'] = sender.full_name or sender.username if sender else 'Unknown'
        
        result.append(tx_dict)
    
    return jsonify({'transactions': result}), 200
