from celery import shared_task
from app.database.mongodb import get_mongo_db
from app.database.postgresql import sync_engine
from sqlalchemy.orm import sessionmaker
from app.models.postgresql_models import Transaction
from datetime import datetime, timedelta
import uuid
from decimal import Decimal


@shared_task(name="categorize_transactions")
def categorize_transactions(user_id: str, batch_size: int = 100):
    """Categorize transactions using rule-based engine"""
    try:
        from app.services.categorization_engine import CategorizationEngine
        from datetime import datetime
        
        db = get_mongo_db()
        parsed_collection = db["parsed_transactions"]
        
        # Get unprocessed transactions
        transactions = list(parsed_collection.find({
            "user_id": user_id,
            "processed": False
        }).limit(batch_size))
        
        if not transactions:
            return {"status": "no_transactions"}
        
        # Initialize categorization engine
        engine = CategorizationEngine(user_id)
        
        categorized_count = 0
        
        for txn in transactions:
            description = str(txn.get("description", ""))
            merchant = str(txn.get("merchant", ""))
            bank = str(txn.get("bank", ""))
            
            # Categorize
            category, confidence = engine.categorize(description, merchant, bank)
            
            # Detect transaction type
            amount = txn.get("amount", 0)
            from decimal import Decimal
            txn_type = engine.detect_transaction_type(description, Decimal(amount))
            
            # Update transaction with category
            parsed_collection.update_one(
                {"_id": txn["_id"]},
                {
                    "$set": {
                        "category": category,
                        "category_confidence": confidence,
                        "transaction_type": txn_type,
                        "processed": True,
                        "categorized_at": datetime.utcnow()
                    }
                }
            )
            
            # Save to PostgreSQL
            save_to_postgres(user_id, txn, category, txn_type)
            categorized_count += 1
        
        return {
            "status": "success",
            "categorized": categorized_count
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@shared_task(name="detect_anomalies")
def detect_anomalies(user_id: str, days: int = 30):
    """Detect anomalous transactions"""
    try:
        # Simple anomaly detection based on amount thresholds
        db = get_mongo_db()
        transactions_collection = db["transactions"]
        
        # Get recent transactions
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        transactions = list(transactions_collection.find({
            "user_id": user_id,
            "transaction_date": {"$gte": cutoff_date}
        }))
        
        if not transactions:
            return {"status": "no_transactions"}
        
        # Calculate average and std
        amounts = [float(t["amount"]) for t in transactions]
        avg_amount = sum(amounts) / len(amounts)
        std_amount = (sum((x - avg_amount) ** 2 for x in amounts) / len(amounts)) ** 0.5
        
        # Detect anomalies (3 std away from mean)
        anomalies = []
        for txn in transactions:
            amount = float(txn["amount"])
            if abs(amount - avg_amount) > 3 * std_amount:
                anomalies.append({
                    "transaction_id": txn["_id"],
                    "anomaly_type": "unusual_amount",
                    "amount": amount,
                    "average": avg_amount,
                    "description": txn.get("description", "")
                })
        
        return {
            "status": "success",
            "anomalies_found": len(anomalies),
            "anomalies": anomalies
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def save_to_postgres(user_id: str, transaction: dict, category: str, txn_type: str):
    """Save transaction to PostgreSQL after processing"""
    from app.models.postgresql_models import TransactionType
    Session = sessionmaker(bind=sync_engine)
    session = Session()
    
    try:
        transaction_obj = Transaction(
            id=str(uuid.uuid4()),
            user_id=user_id,
            amount=float(transaction["amount"]),
            currency="INR",
            transaction_date=datetime.utcnow(),
            description=str(transaction.get("description", "")),
            merchant=str(transaction.get("merchant", "")),
            category=category,
            transaction_type=TransactionType.DEBIT if txn_type == "debit" else TransactionType.CREDIT,
            reference_id=str(transaction.get("_id", "")),
            status="cleared",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        session.add(transaction_obj)
        session.commit()
    except Exception as e:
        session.rollback()
        print(f"Error saving to PostgreSQL: {e}")
    finally:
        session.close()

