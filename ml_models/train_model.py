"""
Machine Learning Fraud Detection Model Training Script
Uses XGBoost and Random Forest for fraud detection
Dataset: PS_20174392719_1491204439457_log.csv (Paysim synthetic financial dataset)
"""
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score
from imblearn.over_sampling import SMOTE
from imblearn.under_sampling import RandomUnderSampler
from imblearn.pipeline import Pipeline
import xgboost as xgb
import joblib
import os
import warnings
warnings.filterwarnings('ignore')


class FraudDetectionModelTrainer:
    """
    Fraud Detection Model Trainer
    Handles data preprocessing, model training, and model persistence
    """
    
    def __init__(self, data_path):
        self.data_path = data_path
        self.model = None
        self.scaler = StandardScaler()
        self.label_encoder = LabelEncoder()
        self.feature_columns = None
        
    def load_data(self, sample_size=None):
        """Load and preprocess the dataset"""
        print("Loading data...")
        
        # Load data (optionally with sampling for faster training)
        if sample_size:
            # Read a sample for faster training
            df = pd.read_csv(self.data_path, nrows=sample_size)
        else:
            df = pd.read_csv(self.data_path)
        
        print(f"Dataset shape: {df.shape}")
        print(f"Fraud cases: {df['isFraud'].sum()} ({df['isFraud'].mean()*100:.2f}%)")
        
        return df
    
    def preprocess_data(self, df):
        """Feature engineering and preprocessing"""
        print("Preprocessing data...")
        
        # Create copy to avoid modifying original
        data = df.copy()
        
        # Feature Engineering
        # 1. Balance difference features
        data['orig_balance_diff'] = data['oldbalanceOrg'] - data['newbalanceOrig']
        data['dest_balance_diff'] = data['newbalanceDest'] - data['oldbalanceDest']
        
        # 2. Balance ratios (handle division by zero)
        data['orig_balance_ratio'] = np.where(
            data['oldbalanceOrg'] > 0,
            data['newbalanceOrig'] / data['oldbalanceOrg'],
            0
        )
        data['dest_balance_ratio'] = np.where(
            data['oldbalanceDest'] > 0,
            data['newbalanceDest'] / data['oldbalanceDest'],
            1
        )
        
        # 3. Error balance features (suspicious if balance change doesn't match amount)
        data['orig_error_balance'] = data['orig_balance_diff'] - data['amount']
        data['dest_error_balance'] = data['dest_balance_diff'] - data['amount']
        
        # 4. Is the origin balance emptied?
        data['is_orig_emptied'] = (data['newbalanceOrig'] == 0).astype(int)
        
        # 5. Transaction amount relative to balance
        data['amount_to_orig_balance'] = np.where(
            data['oldbalanceOrg'] > 0,
            data['amount'] / data['oldbalanceOrg'],
            data['amount']
        )
        
        # 6. Encode transaction type
        data['type_encoded'] = self.label_encoder.fit_transform(data['type'])
        
        # 7. Create binary flags for transaction types (most fraud in TRANSFER and CASH_OUT)
        data['is_transfer'] = (data['type'] == 'TRANSFER').astype(int)
        data['is_cash_out'] = (data['type'] == 'CASH_OUT').astype(int)
        
        # 8. High amount flag
        data['is_high_amount'] = (data['amount'] > data['amount'].quantile(0.95)).astype(int)
        
        # Select features for training
        self.feature_columns = [
            'step', 'type_encoded', 'amount', 
            'oldbalanceOrg', 'newbalanceOrig', 
            'oldbalanceDest', 'newbalanceDest',
            'orig_balance_diff', 'dest_balance_diff',
            'orig_balance_ratio', 'dest_balance_ratio',
            'orig_error_balance', 'dest_error_balance',
            'is_orig_emptied', 'amount_to_orig_balance',
            'is_transfer', 'is_cash_out', 'is_high_amount'
        ]
        
        X = data[self.feature_columns]
        y = data['isFraud']
        
        # Handle infinite values
        X = X.replace([np.inf, -np.inf], 0)
        X = X.fillna(0)
        
        return X, y
    
    def balance_dataset(self, X, y):
        """Balance the dataset using SMOTE and undersampling"""
        print("Balancing dataset...")
        
        # Create a pipeline that first undersamples majority, then oversamples minority
        over = SMOTE(sampling_strategy=0.5, random_state=42)
        under = RandomUnderSampler(sampling_strategy=0.8, random_state=42)
        
        pipeline = Pipeline(steps=[('over', over), ('under', under)])
        X_balanced, y_balanced = pipeline.fit_resample(X, y)
        
        print(f"Balanced dataset shape: {X_balanced.shape}")
        print(f"Balanced fraud ratio: {y_balanced.mean()*100:.2f}%")
        
        return X_balanced, y_balanced
    
    def train_model(self, X, y, model_type='xgboost'):
        """Train the fraud detection model"""
        print(f"Training {model_type} model...")
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        if model_type == 'xgboost':
            self.model = xgb.XGBClassifier(
                n_estimators=100,
                max_depth=6,
                learning_rate=0.1,
                subsample=0.8,
                colsample_bytree=0.8,
                scale_pos_weight=len(y_train[y_train==0]) / len(y_train[y_train==1]),
                random_state=42,
                use_label_encoder=False,
                eval_metric='logloss'
            )
        else:
            self.model = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                min_samples_split=5,
                min_samples_leaf=2,
                class_weight='balanced',
                random_state=42,
                n_jobs=-1
            )
        
        # Train
        self.model.fit(X_train_scaled, y_train)
        
        # Evaluate
        y_pred = self.model.predict(X_test_scaled)
        y_prob = self.model.predict_proba(X_test_scaled)[:, 1]
        
        print("\n=== Model Evaluation ===")
        print("\nClassification Report:")
        print(classification_report(y_test, y_pred, target_names=['Normal', 'Fraud']))
        
        print("\nConfusion Matrix:")
        print(confusion_matrix(y_test, y_pred))
        
        print(f"\nROC-AUC Score: {roc_auc_score(y_test, y_prob):.4f}")
        
        # Feature importance
        if model_type == 'xgboost':
            importance = self.model.feature_importances_
        else:
            importance = self.model.feature_importances_
            
        feature_importance = pd.DataFrame({
            'feature': self.feature_columns,
            'importance': importance
        }).sort_values('importance', ascending=False)
        
        print("\nTop 10 Important Features:")
        print(feature_importance.head(10))
        
        return X_test_scaled, y_test, y_pred, y_prob
    
    def save_model(self, model_dir='ml_models'):
        """Save trained model and preprocessing objects"""
        print(f"\nSaving model to {model_dir}...")
        
        os.makedirs(model_dir, exist_ok=True)
        
        # Save model
        joblib.dump(self.model, os.path.join(model_dir, 'fraud_detection_model.pkl'))
        
        # Save scaler
        joblib.dump(self.scaler, os.path.join(model_dir, 'scaler.pkl'))
        
        # Save label encoder
        joblib.dump(self.label_encoder, os.path.join(model_dir, 'label_encoder.pkl'))
        
        # Save feature columns
        joblib.dump(self.feature_columns, os.path.join(model_dir, 'feature_columns.pkl'))
        
        print("Model saved successfully!")
    
    def run_training_pipeline(self, sample_size=500000, balance_data=True, model_type='xgboost'):
        """Run the complete training pipeline"""
        print("=" * 50)
        print("Starting Fraud Detection Model Training")
        print("=" * 50)
        
        # Load data
        df = self.load_data(sample_size=sample_size)
        
        # Preprocess
        X, y = self.preprocess_data(df)
        
        # Balance dataset (optional but recommended for imbalanced data)
        if balance_data:
            X, y = self.balance_dataset(X, y)
        
        # Train model
        self.train_model(X, y, model_type=model_type)
        
        # Save model
        self.save_model()
        
        print("\n" + "=" * 50)
        print("Training Complete!")
        print("=" * 50)


if __name__ == '__main__':
    # Path to dataset
    DATA_PATH = 'data/PS_20174392719_1491204439457_log.csv'
    
    # Initialize trainer
    trainer = FraudDetectionModelTrainer(DATA_PATH)
    
    # Run training pipeline
    # Using sample for faster training - remove sample_size for full dataset
    trainer.run_training_pipeline(
        sample_size=500000,  # Use 500k samples for faster training
        balance_data=True,
        model_type='xgboost'
    )
