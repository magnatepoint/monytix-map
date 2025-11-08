"""
Exporter service: MongoDB parsed_events → PostgreSQL spendsense.txn_staging
Then triggers ETL to move staging → fact + enriched
"""
from app.database.postgresql import SessionLocal
from app.models.spendsense_models import UploadBatch, TxnStaging
from datetime import datetime, date
import uuid
from decimal import Decimal
from typing import Tuple, List


def _to_date(date_str: str) -> date:
    """
    Parse date string to date object
    
    Args:
        date_str: Date string in various formats
    
    Returns:
        date object or today() if parsing fails
    """
    if not date_str:
        return date.today()
    
    date_str = str(date_str).strip()
    formats = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d.%m.%Y", "%d/%m"]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except:
            continue
    
    # If all formats fail, return today
    return date.today()


def _normalize_amount(amount_str: str) -> Decimal:
    """
    Normalize amount string to Decimal
    
    Args:
        amount_str: Amount as string (may include commas, etc.)
    
    Returns:
        Decimal amount (absolute value)
    """
    if not amount_str:
        return Decimal("0")
    
    # Remove commas and whitespace
    cleaned = str(amount_str).replace(",", "").strip()
    
    try:
        amount_val = Decimal(cleaned)
        return abs(amount_val)  # Always positive for staging
    except:
        return Decimal("0")


def _determine_direction(parsed: dict) -> str:
    """
    Determine transaction direction (debit/credit) from parsed data
    
    Args:
        parsed: Parsed transaction dict
    
    Returns:
        'debit' or 'credit'
    """
    # Check for explicit direction field
    dc = parsed.get("dc") or parsed.get("direction") or parsed.get("type", "").lower()
    
    if dc in ["debit", "dr", "withdrawal", "spent", "payment"]:
        return "debit"
    elif dc in ["credit", "cr", "deposit", "received", "income"]:
        return "credit"
    
    # Infer from amount sign if present
    amount_str = parsed.get("amount") or parsed.get("amount_str", "")
    if amount_str:
        try:
            amount_val = float(str(amount_str).replace(",", ""))
            return "debit" if amount_val < 0 else "credit"
        except:
            pass
    
    # Default to debit for expenses
    return "debit"


def export_parsed_events_to_pg(user_id: str, job_id: str) -> Tuple[int, str, int, List[str]]:
    """
    Reads parsed_events from MongoDB, normalizes, writes to spendsense.txn_staging,
    then triggers ETL to move staging → fact + enriched.
    
    Args:
        user_id: User UUID string
        job_id: Job/source ID (from MongoDB gmail_jobs)
    
    Returns:
        Tuple of (exported_count, upload_id, loaded_to_fact_count, errors)
    """
    errors = []
    exported = 0
    upload_id = None
    loaded_to_fact = 0
    
    # Connect to MongoDB
    try:
        from app.database.mongodb import get_mongo_db
        db = get_mongo_db()
        parsed_col = db["parsed_events"] if db is not None else None
        
        if parsed_col is None:
            errors.append("MongoDB unavailable - cannot export parsed_events")
            return exported, "", loaded_to_fact, errors
    except Exception as e:
        errors.append(f"MongoDB connection error: {e}")
        return exported, "", loaded_to_fact, errors
    
    session = SessionLocal()
    try:
        # 1) Create upload batch in PostgreSQL
        ub = UploadBatch(
            upload_id=uuid.uuid4(),
            user_id=uuid.UUID(user_id),
            source_type='email',
            file_name=None,
            total_records=0,
            parsed_records=0,
            status='received'
        )
        session.add(ub)
        session.commit()
        upload_id = ub.upload_id
        
        # 2) Pull parsed_events that are ready for export (status='parsed' or 'cleaned')
        # Note: job_id might be None, so make it optional in query
        query_filter = {
            "user_id": user_id,
            "status": {"$in": ["parsed", "cleaned"]}
        }
        if job_id:
            query_filter["job_id"] = job_id
        
        cursor = parsed_col.find(query_filter)
        
        total_found = 0
        for ev in cursor:
            total_found += 1
            
            try:
                p = ev.get("parsed", {})
                if not p:
                    errors.append(f"Parsed event {ev.get('_id')} has no parsed data")
                    continue
                
                # Normalize fields
                date_str = p.get("date") or p.get("date_str", "")
                amount_str = p.get("amount") or p.get("amount_str", "0")
                amount_num = _normalize_amount(amount_str)
                direction = _determine_direction(p)
                
                # Description from parsed data or fallback
                descr = p.get("description") or p.get("pattern") or p.get("narration") or ""
                merchant = p.get("merchant") or p.get("merchant_name") or None
                account_ref = p.get("acct") or p.get("account_hint") or p.get("account_ref") or None
                txn_external_id = p.get("ref") or p.get("reference") or p.get("transaction_id") or None
                
                # Parse date
                txn_date = _to_date(date_str)
                
                # Create staging record
                staging = TxnStaging(
                    upload_id=upload_id,
                    user_id=uuid.UUID(user_id),
                    raw_txn_id=txn_external_id,
                    txn_date=txn_date,
                    description_raw=descr if descr else None,
                    amount=amount_num,
                    direction=direction,
                    currency=p.get("currency", "INR") or "INR",
                    merchant_raw=merchant,
                    account_ref=account_ref,
                    parsed_ok=True,
                    parsed_event_oid=str(ev.get("_id"))  # Link to MongoDB document
                )
                session.add(staging)
                exported += 1
                
                # Mark as exported in MongoDB
                parsed_col.update_one(
                    {"_id": ev["_id"]},
                    {
                        "$set": {
                            "status": "exported",
                            "exported_at": datetime.utcnow(),
                            "pg_upload_id": str(upload_id)
                        }
                    }
                )
                
            except Exception as e:
                errors.append(f"Error exporting parsed_event {ev.get('_id')}: {str(e)}")
                # Mark as error in MongoDB
                parsed_col.update_one(
                    {"_id": ev["_id"]},
                    {"$set": {"status": "error", "error": str(e)}}
                )
                continue
        
        # 3) Update upload batch
        ub.total_records = total_found
        ub.parsed_records = exported
        ub.status = 'parsed' if exported > 0 else 'failed'
        if errors:
            ub.error_json = {"export_errors": errors[:10]}
        session.commit()
        
        # 4) ETL: staging → fact/enriched
        if exported > 0:
            try:
                from app.routers.etl import load_staging_for_user
                loaded_to_fact = load_staging_for_user(user_id)
                print(f"✅ Exported {exported} parsed_events → staged {exported} → loaded {loaded_to_fact} to fact table")
            except Exception as e:
                error_msg = f"ETL error: {e}"
                errors.append(error_msg)
                print(f"⚠️  {error_msg}")
        
        return exported, str(upload_id) if upload_id else "", loaded_to_fact, errors
        
    except Exception as e:
        session.rollback()
        errors.append(f"Export error: {str(e)}")
        import traceback
        print(f"❌ Export error: {e}")
        print(traceback.format_exc())
        return exported, str(upload_id) if upload_id else "", loaded_to_fact, errors
    finally:
        session.close()

