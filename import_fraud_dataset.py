"""
Import PaySim fraud detection dataset into the database
"""
import os
import sys
import pandas as pd
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import FraudTrainingData

def import_dataset(csv_path, sample_size=10000):
    """Import PaySim dataset into database
    
    Args:
        csv_path: Path to the CSV file
        sample_size: Number of records to import (default 10000 for demo)
    """
    app = create_app()
    
    with app.app_context():
        # Create tables if they don't exist
        db.create_all()
        
        print(f"📂 Loading dataset from: {csv_path}")
        
        # Check if data already exists
        existing_count = FraudTrainingData.query.count()
        if existing_count > 0:
            print(f"⚠️  Database already contains {existing_count} records")
            response = input("Do you want to clear existing data and reimport? (y/n): ")
            if response.lower() == 'y':
                FraudTrainingData.query.delete()
                db.session.commit()
                print("✅ Existing data cleared")
            else:
                print("❌ Import cancelled")
                return
        
        # Load CSV file
        try:
            # For large files, use chunked reading
            print(f"📖 Reading CSV file...")
            
            # Read with specific columns to save memory
            df = pd.read_csv(csv_path, nrows=sample_size)
            
            print(f"📊 Dataset shape: {df.shape}")
            print(f"📋 Columns: {list(df.columns)}")
            
            # Get fraud statistics
            fraud_count = df['isFraud'].sum() if 'isFraud' in df.columns else 0
            print(f"🔍 Fraud transactions: {fraud_count} ({fraud_count/len(df)*100:.2f}%)")
            
            # Import records
            print(f"💾 Importing {len(df)} records...")
            
            batch_size = 1000
            imported = 0
            
            for i in range(0, len(df), batch_size):
                batch = df.iloc[i:i+batch_size]
                
                records = []
                for _, row in batch.iterrows():
                    record = FraudTrainingData(
                        step=int(row.get('step', 0)),
                        transaction_type=str(row.get('type', 'TRANSFER')),
                        amount=float(row.get('amount', 0)),
                        name_orig=str(row.get('nameOrig', 'C0000000000')),
                        old_balance_orig=float(row.get('oldbalanceOrg', 0)),
                        new_balance_orig=float(row.get('newbalanceOrig', 0)),
                        name_dest=str(row.get('nameDest', 'C0000000000')),
                        old_balance_dest=float(row.get('oldbalanceDest', 0)),
                        new_balance_dest=float(row.get('newbalanceDest', 0)),
                        is_fraud=bool(row.get('isFraud', 0)),
                        is_flagged_fraud=bool(row.get('isFlaggedFraud', 0))
                    )
                    records.append(record)
                
                db.session.bulk_save_objects(records)
                db.session.commit()
                
                imported += len(batch)
                print(f"  Progress: {imported}/{len(df)} ({imported/len(df)*100:.1f}%)")
            
            print(f"\n✅ Successfully imported {imported} records!")
            
            # Verify import
            final_count = FraudTrainingData.query.count()
            fraud_in_db = FraudTrainingData.query.filter_by(is_fraud=True).count()
            print(f"📊 Database now contains: {final_count} records")
            print(f"🔍 Fraud records: {fraud_in_db} ({fraud_in_db/final_count*100:.2f}%)")
            
        except FileNotFoundError:
            print(f"❌ Error: File not found: {csv_path}")
            return
        except Exception as e:
            print(f"❌ Error importing dataset: {e}")
            db.session.rollback()
            raise


def get_training_data_from_db(limit=None):
    """Retrieve training data from database"""
    app = create_app()
    
    with app.app_context():
        query = FraudTrainingData.query
        if limit:
            query = query.limit(limit)
        
        records = query.all()
        
        data = []
        for r in records:
            data.append({
                'step': r.step,
                'type': r.transaction_type,
                'amount': r.amount,
                'nameOrig': r.name_orig,
                'oldbalanceOrg': r.old_balance_orig,
                'newbalanceOrig': r.new_balance_orig,
                'nameDest': r.name_dest,
                'oldbalanceDest': r.old_balance_dest,
                'newbalanceDest': r.new_balance_dest,
                'isFraud': int(r.is_fraud),
                'isFlaggedFraud': int(r.is_flagged_fraud)
            })
        
        return pd.DataFrame(data)


if __name__ == '__main__':
    # Default path to dataset
    dataset_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'securebank-frontend', 'ml_model', 'archive', 'PS_20174392719_1491204439457_log.csv'
    )
    
    # Allow custom path from command line
    if len(sys.argv) > 1:
        dataset_path = sys.argv[1]
    
    # Allow custom sample size
    sample_size = 10000  # Default to 10k records for demo
    if len(sys.argv) > 2:
        sample_size = int(sys.argv[2])
    
    import_dataset(dataset_path, sample_size)
