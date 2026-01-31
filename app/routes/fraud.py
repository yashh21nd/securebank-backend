"""
Fraud Detection Routes
Handles fraud detection API endpoints
"""
from flask import Blueprint, request, jsonify
from app.routes.auth import token_required

fraud_bp = Blueprint('fraud', __name__)


def get_db():
    from app import db
    return db


def get_models():
    from app.models import FraudAlert, Transaction, User
    return FraudAlert, Transaction, User


def get_fraud_service():
    from app.services.fraud_detection import fraud_service
    return fraud_service


@fraud_bp.route('/check', methods=['POST'])
@token_required
def check_transaction(current_user):
    """
    Check a transaction for potential fraud
    """
    data = request.get_json()
    fraud_service = get_fraud_service()
    
    # Required fields for fraud check
    transaction_data = {
        'type': data.get('type', 'TRANSFER'),
        'amount': data.get('amount', 0),
        'oldbalanceOrg': data.get('sender_balance', 0),
        'newbalanceOrig': data.get('sender_balance', 0) - data.get('amount', 0),
        'oldbalanceDest': data.get('receiver_balance', 0),
        'newbalanceDest': data.get('receiver_balance', 0) + data.get('amount', 0),
        'step': data.get('hour', 12)
    }
    
    result = fraud_service.predict_fraud(transaction_data)
    
    return jsonify({
        'fraud_check': result,
        'recommendation': 'block' if result['should_block'] else ('flag' if result['should_flag'] else 'allow')
    }), 200


@fraud_bp.route('/alerts', methods=['GET'])
@token_required
def get_fraud_alerts(current_user):
    """Get fraud alerts for the user"""
    FraudAlert, Transaction, User = get_models()
    
    alerts = FraudAlert.query.filter_by(user_id=current_user.id).order_by(
        FraudAlert.created_at.desc()
    ).limit(50).all()
    
    return jsonify({
        'alerts': [alert.to_dict() for alert in alerts]
    }), 200


@fraud_bp.route('/alerts/<alert_id>/review', methods=['POST'])
@token_required
def review_alert(current_user, alert_id):
    """Review and update a fraud alert status"""
    data = request.get_json()
    db = get_db()
    FraudAlert, Transaction, User = get_models()
    
    alert = FraudAlert.query.filter_by(id=alert_id, user_id=current_user.id).first()
    
    if not alert:
        return jsonify({'error': 'Alert not found'}), 404
    
    status = data.get('status')  # confirmed, dismissed
    if status not in ['confirmed', 'dismissed']:
        return jsonify({'error': 'Invalid status'}), 400
    
    from datetime import datetime
    alert.status = status
    alert.reviewed_by = current_user.id
    alert.reviewed_at = datetime.utcnow()
    
    db.session.commit()
    
    return jsonify({
        'message': f'Alert {status}',
        'alert': alert.to_dict()
    }), 200


@fraud_bp.route('/model/info', methods=['GET'])
@token_required
def get_model_info(current_user):
    """Get information about the fraud detection model"""
    fraud_service = get_fraud_service()
    
    return jsonify(fraud_service.get_model_info()), 200


@fraud_bp.route('/model/load', methods=['POST'])
@token_required
def load_model(current_user):
    """Load/reload the fraud detection model"""
    fraud_service = get_fraud_service()
    
    success = fraud_service.load_model()
    
    if success:
        return jsonify({'message': 'Model loaded successfully'}), 200
    else:
        return jsonify({'error': 'Failed to load model'}), 500


@fraud_bp.route('/statistics', methods=['GET'])
@token_required
def get_fraud_statistics(current_user):
    """Get fraud detection statistics"""
    FraudAlert, Transaction, User = get_models()
    from sqlalchemy import func
    from datetime import datetime, timedelta
    
    # Get statistics for last 30 days
    start_date = datetime.utcnow() - timedelta(days=30)
    
    # Total alerts
    total_alerts = FraudAlert.query.filter(
        FraudAlert.user_id == current_user.id,
        FraudAlert.created_at >= start_date
    ).count()
    
    # Alerts by status
    alerts_by_status = FraudAlert.query.filter(
        FraudAlert.user_id == current_user.id,
        FraudAlert.created_at >= start_date
    ).with_entities(
        FraudAlert.status,
        func.count(FraudAlert.id)
    ).group_by(FraudAlert.status).all()
    
    # Flagged transactions
    flagged_count = Transaction.query.filter(
        (Transaction.sender_id == current_user.id) | (Transaction.receiver_id == current_user.id),
        Transaction.is_flagged == True,
        Transaction.created_at >= start_date
    ).count()
    
    # Blocked transactions
    blocked_count = Transaction.query.filter(
        Transaction.sender_id == current_user.id,
        Transaction.status == 'blocked',
        Transaction.created_at >= start_date
    ).count()
    
    return jsonify({
        'period_days': 30,
        'statistics': {
            'total_alerts': total_alerts,
            'alerts_by_status': {status: count for status, count in alerts_by_status},
            'flagged_transactions': flagged_count,
            'blocked_transactions': blocked_count
        }
    }), 200
# Add these demo/public endpoints at the end of fraud.py

@fraud_bp.route('/analyze', methods=['POST'])
def analyze_transaction_public():
    """Public endpoint for fraud analysis (demo mode)"""
    data = request.get_json()
    fraud_service = get_fraud_service()

    transaction_data = {
        'type': data.get('transaction_type', 'TRANSFER').upper(),
        'amount': float(data.get('amount', 0)),
        'oldbalanceOrg': float(data.get('sender_balance', 10000)),
        'newbalanceOrig': float(data.get('sender_balance', 10000)) - float(data.get('amount', 0)),
        'oldbalanceDest': float(data.get('recipient_balance', 5000)),
        'newbalanceDest': float(data.get('recipient_balance', 5000)) + float(data.get('amount', 0)),
        'step': data.get('hour', 12)
    }

    result = fraud_service.predict_fraud(transaction_data)

    return jsonify({
        'status': 'success',
        'is_fraudulent': result.get('is_fraud', False),
        'fraud_probability': result.get('fraud_probability', 0),
        'risk_score': result.get('fraud_probability', 0) * 100,
        'risk_level': 'critical' if result.get('fraud_probability', 0) > 0.7 else 'high' if result.get('fraud_probability', 0) > 0.5 else 'medium' if result.get('fraud_probability', 0) > 0.3 else 'low',
        'should_block': result.get('should_block', False),
        'should_flag': result.get('should_flag', False),
        'recommendation': result.get('recommendation', 'Transaction appears safe'),
        'analysis': {
            'amount_risk': 'High' if float(data.get('amount', 0)) > 50000 else 'Normal',
            'pattern_risk': 'Normal'
        }
    }), 200


@fraud_bp.route('/health', methods=['GET'])
def fraud_health():
    """Public health check for fraud service"""
    fraud_service = get_fraud_service()
    model_info = fraud_service.get_model_info()
    
    return jsonify({
        'status': 'healthy',
        'model_loaded': model_info.get('model_loaded', False),
        'model_type': model_info.get('model_type', 'RandomForest'),
        'features': model_info.get('n_features', 21)
    }), 200
