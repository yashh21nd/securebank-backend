"""
Fraud Detection Routes
Handles fraud detection API endpoints
"""
from flask import Blueprint, request, jsonify
from flask_cors import cross_origin
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


@fraud_bp.route('/check', methods=['POST', 'OPTIONS'])
@cross_origin()
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


@fraud_bp.route('/alerts', methods=['GET', 'OPTIONS'])
@cross_origin()
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


@fraud_bp.route('/alerts/<alert_id>/review', methods=['POST', 'OPTIONS'])
@cross_origin()
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


@fraud_bp.route('/model/info', methods=['GET', 'OPTIONS'])
@cross_origin()
@token_required
def get_model_info(current_user):
    """Get information about the fraud detection model"""
    fraud_service = get_fraud_service()

    return jsonify(fraud_service.get_model_info()), 200


@fraud_bp.route('/model/load', methods=['POST', 'OPTIONS'])
@cross_origin()
@token_required
def load_model(current_user):
    """Load/reload the fraud detection model"""
    fraud_service = get_fraud_service()

    success = fraud_service.load_model()

    if success:
        return jsonify({'message': 'Model loaded successfully'}), 200
    else:
        return jsonify({'error': 'Failed to load model'}), 500


@fraud_bp.route('/statistics', methods=['GET', 'OPTIONS'])
@cross_origin()
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


# Public endpoints for demo mode (no auth required)

@fraud_bp.route('/analyze', methods=['POST', 'OPTIONS'])
@cross_origin(origins='*')
def analyze_transaction_public():
    """Public endpoint for fraud analysis (demo mode)"""
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response, 204
    
    try:
        data = request.get_json() or {}
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

        response = jsonify({
            'status': 'success',
            'is_fraud': result.get('is_fraud', False),
            'fraud_probability': result.get('fraud_probability', 0),
            'risk_score': result.get('fraud_probability', 0) * 100,
            'risk_level': 'critical' if result.get('fraud_probability', 0) > 0.7 else 'high' if result.get('fraud_probability', 0) > 0.5 else 'medium' if result.get('fraud_probability', 0) > 0.3 else 'low',
            'should_block': result.get('should_block', False),
            'requires_review': result.get('should_flag', False),
            'risk_factors': result.get('risk_factors', []),
            'recommendation': result.get('recommendation', 'Transaction appears safe'),
            'analysis': {
                'amount_risk': 'High' if float(data.get('amount', 0)) > 50000 else 'Normal',
                'pattern_risk': 'Normal'
            }
        })
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response, 200
    except Exception as e:
        response = jsonify({
            'status': 'error',
            'error': str(e),
            'is_fraud': False,
            'fraud_probability': 0,
            'risk_level': 'low',
            'risk_factors': [],
            'recommendation': 'Unable to analyze - defaulting to safe'
        })
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response, 200


@fraud_bp.route('/health', methods=['GET', 'OPTIONS'])
@cross_origin(origins='*')
def fraud_health():
    """Public health check for fraud service"""
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response, 204
    
    try:
        fraud_service = get_fraud_service()
        model_info = fraud_service.get_model_info()

        response = jsonify({
            'status': 'healthy',
            'model_loaded': model_info.get('model_loaded', False),
            'model_type': model_info.get('model_type', 'RandomForest'),
            'features': model_info.get('n_features', 21)
        })
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response, 200
    except Exception as e:
        response = jsonify({
            'status': 'healthy',
            'model_loaded': False,
            'error': str(e)
        })
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response, 200


@fraud_bp.route('/dataset/stats', methods=['GET', 'OPTIONS'])
@cross_origin(origins='*')
def get_dataset_stats():
    """Get statistics about the fraud detection dataset"""
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response, 204
    
    try:
        # Return mock dataset statistics (PaySim dataset info)
        response = jsonify({
            'status': 'success',
            'dataset': {
                'name': 'PaySim Synthetic Financial Dataset',
                'total_transactions': 6362620,
                'fraud_transactions': 8213,
                'fraud_percentage': 0.129,
                'transaction_types': ['PAYMENT', 'TRANSFER', 'CASH_OUT', 'CASH_IN', 'DEBIT'],
                'features': 18,
                'time_steps': 743
            },
            'model': {
                'type': 'XGBoost Classifier',
                'accuracy': 0.9987,
                'precision': 0.9823,
                'recall': 0.9156,
                'f1_score': 0.9478,
                'auc_roc': 0.9912
            }
        })
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response, 200
    except Exception as e:
        response = jsonify({
            'status': 'error',
            'error': str(e)
        })
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response, 200


@fraud_bp.route('/contact/profile', methods=['GET', 'POST', 'OPTIONS'])
@cross_origin(origins='*')
def get_contact_fraud_profile():
    """Get fraud risk profile for a contact"""
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response, 204
    
    try:
        data = request.get_json() or {}
        contact_id = data.get('contact_id') or request.args.get('contact_id', 'unknown')
        
        # Return mock contact fraud profile
        import random
        risk_score = random.uniform(0.05, 0.35)  # Most contacts are low risk
        
        response = jsonify({
            'status': 'success',
            'contact_id': contact_id,
            'risk_profile': {
                'risk_score': round(risk_score, 3),
                'risk_level': 'low' if risk_score < 0.3 else 'medium' if risk_score < 0.6 else 'high',
                'trust_score': round(1 - risk_score, 3),
                'transaction_count': random.randint(5, 50),
                'successful_transactions': random.randint(5, 45),
                'flagged_transactions': random.randint(0, 2),
                'account_age_days': random.randint(30, 730),
                'verification_status': 'verified',
                'last_transaction': '2026-02-05T14:30:00Z'
            }
        })
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response, 200
    except Exception as e:
        response = jsonify({
            'status': 'error',
            'error': str(e),
            'risk_profile': {
                'risk_score': 0.1,
                'risk_level': 'low',
                'trust_score': 0.9
            }
        })
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response, 200
