"""
Fraud Detection Service
Real-time fraud detection using trained ML model
"""
import numpy as np
import joblib
import os
from datetime import datetime


class FraudDetectionService:
    """
    Fraud Detection Service for real-time transaction analysis
    """
    
    def __init__(self, model_dir='ml_models'):
        self.model_dir = model_dir
        self.model = None
        self.scaler = None
        self.label_encoder = None
        self.feature_columns = None
        self.is_loaded = False
        
        # Transaction type mapping
        self.type_mapping = {
            'PAYMENT': 0,
            'TRANSFER': 1,
            'CASH_OUT': 2,
            'CASH_IN': 3,
            'DEBIT': 4
        }
        
    def load_model(self):
        """Load the trained model and preprocessing objects"""
        try:
            model_path = os.path.join(self.model_dir, 'fraud_detection_model.pkl')
            scaler_path = os.path.join(self.model_dir, 'scaler.pkl')
            encoder_path = os.path.join(self.model_dir, 'label_encoder.pkl')
            features_path = os.path.join(self.model_dir, 'feature_columns.pkl')
            
            if os.path.exists(model_path):
                self.model = joblib.load(model_path)
                self.scaler = joblib.load(scaler_path)
                self.label_encoder = joblib.load(encoder_path)
                self.feature_columns = joblib.load(features_path)
                self.is_loaded = True
                print("Fraud detection model loaded successfully!")
                return True
            else:
                print("Model files not found. Please train the model first.")
                return False
        except Exception as e:
            print(f"Error loading model: {e}")
            return False
    
    def extract_features(self, transaction_data):
        """
        Extract features from transaction data for prediction
        
        Args:
            transaction_data: dict with keys:
                - type: str (PAYMENT, TRANSFER, CASH_OUT, CASH_IN, DEBIT)
                - amount: float
                - oldbalanceOrg: float (sender's balance before)
                - newbalanceOrig: float (sender's balance after)
                - oldbalanceDest: float (receiver's balance before)
                - newbalanceDest: float (receiver's balance after)
                - step: int (time step, can be hour of day * some factor)
        
        Returns:
            numpy array of features
        """
        # Extract base features
        step = transaction_data.get('step', datetime.now().hour)
        tx_type = transaction_data.get('type', 'PAYMENT')
        amount = transaction_data.get('amount', 0)
        old_balance_org = transaction_data.get('oldbalanceOrg', 0)
        new_balance_orig = transaction_data.get('newbalanceOrig', old_balance_org - amount)
        old_balance_dest = transaction_data.get('oldbalanceDest', 0)
        new_balance_dest = transaction_data.get('newbalanceDest', old_balance_dest + amount)
        
        # Encode transaction type
        type_encoded = self.type_mapping.get(tx_type, 0)
        
        # Calculate derived features
        orig_balance_diff = old_balance_org - new_balance_orig
        dest_balance_diff = new_balance_dest - old_balance_dest
        
        orig_balance_ratio = new_balance_orig / old_balance_org if old_balance_org > 0 else 0
        dest_balance_ratio = new_balance_dest / old_balance_dest if old_balance_dest > 0 else 1
        
        orig_error_balance = orig_balance_diff - amount
        dest_error_balance = dest_balance_diff - amount
        
        is_orig_emptied = 1 if new_balance_orig == 0 else 0
        
        amount_to_orig_balance = amount / old_balance_org if old_balance_org > 0 else amount
        
        is_transfer = 1 if tx_type == 'TRANSFER' else 0
        is_cash_out = 1 if tx_type == 'CASH_OUT' else 0
        is_high_amount = 1 if amount > 200000 else 0  # Threshold for high amount
        
        # Create feature array in correct order
        features = np.array([
            step,
            type_encoded,
            amount,
            old_balance_org,
            new_balance_orig,
            old_balance_dest,
            new_balance_dest,
            orig_balance_diff,
            dest_balance_diff,
            orig_balance_ratio,
            dest_balance_ratio,
            orig_error_balance,
            dest_error_balance,
            is_orig_emptied,
            amount_to_orig_balance,
            is_transfer,
            is_cash_out,
            is_high_amount
        ]).reshape(1, -1)
        
        # Handle infinite values
        features = np.nan_to_num(features, nan=0, posinf=0, neginf=0)
        
        return features
    
    def predict_fraud(self, transaction_data):
        """
        Predict if a transaction is fraudulent
        
        Args:
            transaction_data: dict with transaction details
            
        Returns:
            dict with:
                - is_fraud: bool
                - fraud_probability: float (0-1)
                - risk_level: str (low, medium, high, critical)
                - risk_factors: list of identified risk factors
        """
        if not self.is_loaded:
            # If model not loaded, use rule-based detection
            return self._rule_based_detection(transaction_data)
        
        try:
            # Extract features
            features = self.extract_features(transaction_data)
            
            # Scale features
            features_scaled = self.scaler.transform(features)
            
            # Predict
            prediction = self.model.predict(features_scaled)[0]
            probability = self.model.predict_proba(features_scaled)[0][1]
            
            # Determine risk level
            if probability < 0.3:
                risk_level = 'low'
            elif probability < 0.5:
                risk_level = 'medium'
            elif probability < 0.7:
                risk_level = 'high'
            else:
                risk_level = 'critical'
            
            # Identify risk factors
            risk_factors = self._identify_risk_factors(transaction_data, probability)
            
            return {
                'is_fraud': bool(prediction),
                'fraud_probability': float(probability),
                'risk_level': risk_level,
                'risk_factors': risk_factors,
                'should_flag': probability > 0.5,
                'should_block': probability > 0.8
            }
            
        except Exception as e:
            print(f"Error in fraud prediction: {e}")
            return self._rule_based_detection(transaction_data)
    
    def _rule_based_detection(self, transaction_data):
        """
        Fallback rule-based fraud detection when ML model is not available
        """
        risk_factors = []
        risk_score = 0.0
        
        amount = transaction_data.get('amount', 0)
        tx_type = transaction_data.get('type', 'PAYMENT')
        old_balance = transaction_data.get('oldbalanceOrg', 0)
        new_balance = transaction_data.get('newbalanceOrig', old_balance)
        
        # Rule 1: Large transaction amount
        if amount > 100000:
            risk_score += 0.2
            risk_factors.append('Large transaction amount')
        
        # Rule 2: Account emptied
        if new_balance == 0 and old_balance > 0:
            risk_score += 0.3
            risk_factors.append('Account completely emptied')
        
        # Rule 3: High-risk transaction types
        if tx_type in ['TRANSFER', 'CASH_OUT']:
            risk_score += 0.1
            risk_factors.append(f'High-risk transaction type: {tx_type}')
        
        # Rule 4: Amount exceeds balance
        if amount > old_balance * 0.9:
            risk_score += 0.2
            risk_factors.append('Transaction amount is most of the balance')
        
        # Rule 5: Unusual time (if available)
        step = transaction_data.get('step', 12)
        if step < 6 or step > 22:  # Unusual hours
            risk_score += 0.1
            risk_factors.append('Transaction at unusual time')
        
        # Cap risk score at 1.0
        risk_score = min(risk_score, 1.0)
        
        # Determine risk level
        if risk_score < 0.3:
            risk_level = 'low'
        elif risk_score < 0.5:
            risk_level = 'medium'
        elif risk_score < 0.7:
            risk_level = 'high'
        else:
            risk_level = 'critical'
        
        return {
            'is_fraud': risk_score > 0.5,
            'fraud_probability': risk_score,
            'risk_level': risk_level,
            'risk_factors': risk_factors,
            'should_flag': risk_score > 0.5,
            'should_block': risk_score > 0.8,
            'detection_method': 'rule_based'
        }
    
    def _identify_risk_factors(self, transaction_data, probability):
        """Identify specific risk factors for a transaction"""
        risk_factors = []
        
        amount = transaction_data.get('amount', 0)
        tx_type = transaction_data.get('type', 'PAYMENT')
        old_balance = transaction_data.get('oldbalanceOrg', 0)
        new_balance = transaction_data.get('newbalanceOrig', old_balance)
        
        if amount > 100000:
            risk_factors.append('Large transaction amount detected')
        
        if new_balance == 0 and old_balance > 0:
            risk_factors.append('Account balance will be emptied')
        
        if tx_type in ['TRANSFER', 'CASH_OUT']:
            risk_factors.append(f'Transaction type ({tx_type}) is commonly associated with fraud')
        
        if amount > old_balance * 0.8:
            risk_factors.append('Transaction amount exceeds 80% of current balance')
        
        if probability > 0.7:
            risk_factors.append('ML model detected high fraud probability pattern')
        
        return risk_factors
    
    def batch_predict(self, transactions_list):
        """
        Predict fraud for multiple transactions
        
        Args:
            transactions_list: list of transaction dicts
            
        Returns:
            list of prediction results
        """
        return [self.predict_fraud(tx) for tx in transactions_list]
    
    def get_model_info(self):
        """Get information about the loaded model"""
        if not self.is_loaded:
            return {'status': 'not_loaded', 'message': 'Model not loaded'}
        
        return {
            'status': 'loaded',
            'model_type': type(self.model).__name__,
            'features': self.feature_columns,
            'feature_count': len(self.feature_columns) if self.feature_columns else 0
        }


# Global instance
import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
fraud_service = FraudDetectionService(os.path.join(BASE_DIR, 'ml_models'))

