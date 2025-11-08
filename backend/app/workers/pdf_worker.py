from celery import shared_task
import pdfplumber
import PyPDF2
import io
from app.database.mongodb import get_mongo_db
from app.database.postgresql import SessionLocal
from app.models.spendsense_models import UploadBatch, TxnStaging
from datetime import datetime, date
import re
import uuid
from decimal import Decimal


@shared_task(name="parse_pdf")
def parse_pdf(user_id: str, source_id: str, file_content: bytes, bank: str = "unknown", password: str = None):
    """
    Parse PDF files and load to spendsense.txn_staging
    
    Flow: MongoDB (job tracking) → PostgreSQL spendsense.txn_staging
    """
    session = SessionLocal()
    
    try:
        # Connect to MongoDB for job tracking
        db = get_mongo_db()
        uploads_collection = db["upload_jobs"]
        
        # Get file name from MongoDB job if available
        job = uploads_collection.find_one({"_id": source_id})
        file_name = job.get("file_name") if job else None
        
        # Update job status to 'processing'
        uploads_collection.update_one(
            {"_id": source_id},
            {"$set": {"status": "processing", "started_at": datetime.utcnow()}}
        )
        
        # Check if PDF is password protected
        is_encrypted = False
        try:
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
            is_encrypted = pdf_reader.is_encrypted
        except:
            pass
        
        if is_encrypted and not password:
            # Update MongoDB job status
            uploads_collection.update_one(
                {"_id": source_id},
                {"$set": {"status": "failed", "error": "PDF is password protected", "failed_at": datetime.utcnow()}}
            )
            return {
                "status": "error",
                "error": "PDF is password protected",
                "requires_password": True,
                "bank": bank
            }
        
        # Extract text from PDF
        text = ""
        try:
            if password:
                with pdfplumber.open(io.BytesIO(file_content), password=password) as pdf:
                    for page in pdf.pages:
                        text += page.extract_text() or ""
            else:
                with pdfplumber.open(io.BytesIO(file_content)) as pdf:
                    for page in pdf.pages:
                        text += page.extract_text() or ""
        except Exception as e:
            # Fallback to PyPDF2
            try:
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
                if password:
                    pdf_reader.decrypt(password)
                for page in pdf_reader.pages:
                    text += page.extract_text()
            except Exception as e2:
                uploads_collection.update_one(
                    {"_id": source_id},
                    {"$set": {"status": "failed", "error": str(e2), "failed_at": datetime.utcnow()}}
                )
                return {
                    "status": "error",
                    "error": f"Failed to parse PDF: {str(e2)}",
                    "requires_password": "wrong_password" in str(e2).lower()
                }
        
        # Parse transactions based on bank
        if bank.lower() in ["hdfc", "hdfc bank"]:
            transactions = parse_hdfc_statement(text)
        elif bank.lower() in ["icici", "icici bank"]:
            transactions = parse_icici_statement(text)
        elif bank.lower() in ["sbi", "state bank of india"]:
            transactions = parse_sbi_statement(text)
        else:
            transactions = parse_generic_statement(text)
        
        if not transactions:
            uploads_collection.update_one(
                {"_id": source_id},
                {"$set": {"status": "completed", "parsed_count": 0, "completed_at": datetime.utcnow()}}
            )
            return {
                "status": "success",
                "count": 0,
                "message": "No transactions found in PDF"
            }
        
        # Create upload batch in PostgreSQL (spendsense.upload_batch)
        upload_batch = UploadBatch(
            upload_id=uuid.uuid4(),
            user_id=uuid.UUID(user_id),
            source_type='file',
            file_name=file_name,
            total_records=len(transactions),
            parsed_records=0,
            status='received'
        )
        session.add(upload_batch)
        session.commit()
        
        upload_id = upload_batch.upload_id
        
        staged_count = 0
        errors = []
        
        # Parse and stage transactions to spendsense.txn_staging
        for idx, txn in enumerate(transactions):
            try:
                # Parse date
                txn_date_str = txn.get('date', str(datetime.utcnow().date()))
                txn_date = None
                if txn_date_str:
                    for fmt in ['%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y', '%Y/%m/%d', '%d.%m.%Y', '%d/%m']:
                        try:
                            txn_date = datetime.strptime(str(txn_date_str).strip(), fmt).date()
                            break
                        except:
                            continue
                
                if not txn_date:
                    txn_date = date.today()
                
                # Parse amount
                amount_val = float(txn.get('amount', 0))
                amount = Decimal(str(abs(amount_val)))
                
                # Determine direction (debit/credit)
                direction = txn.get('transaction_type', 'debit').lower()
                if direction not in ['debit', 'credit']:
                    direction = 'debit' if amount_val < 0 else 'credit'
                
                # Get description
                description = str(txn.get('description', 'Unknown')).strip()
                
                # Create staging record
                staged_txn = TxnStaging(
                    upload_id=upload_id,
                    user_id=uuid.UUID(user_id),
                    raw_txn_id=str(txn.get('reference_id', '')),
                    txn_date=txn_date,
                    description_raw=description,
                    amount=amount,
                    direction=direction,
                    currency=txn.get('currency', 'INR'),
                    merchant_raw=str(txn.get('merchant', '')).strip() or None,
                    parsed_ok=True
                )
                session.add(staged_txn)
                staged_count += 1
                
            except Exception as e:
                errors.append(f"Transaction {idx+1}: {str(e)}")
        
        # Update upload batch
        upload_batch.parsed_records = staged_count
        upload_batch.status = 'parsed' if staged_count > 0 else 'failed'
        if errors:
            upload_batch.error_json = {"parse_errors": errors}
        session.commit()
        
        # Update MongoDB job status
        uploads_collection.update_one(
            {"_id": source_id},
            {"$set": {
                "status": "completed",
                "parsed_count": staged_count,
                "completed_at": datetime.utcnow()
            }}
        )
        
        return {
            "status": "success",
            "count": staged_count,
            "upload_id": str(upload_id),
            "total_parsed": len(transactions),
            "errors": errors[:10],
            "bank": bank
        }
        
    except Exception as e:
        session.rollback()
        # Update MongoDB job status to failed
        try:
            db = get_mongo_db()
            uploads_collection = db["upload_jobs"]
            uploads_collection.update_one(
                {"_id": source_id},
                {"$set": {"status": "failed", "error": str(e), "failed_at": datetime.utcnow()}}
            )
        except:
            pass
        return {"status": "error", "error": str(e)}
    finally:
        session.close()


def parse_hdfc_statement(text: str) -> list:
    """Parse HDFC bank statement"""
    transactions = []
    # Pattern matching for HDFC format
    # DATE\s+PARTICULARS\s+WITHDRAWAL\s+DEPOSIT\s+BALANCE
    pattern = r'(\d{2}/\d{2}/\d{4})\s+(.+?)\s+(\d+\.\d{2})?\s+(\d+\.\d{2})?\s+(\d+\.\d{2})'
    
    for match in re.finditer(pattern, text):
        transactions.append({
            "date": match.group(1),
            "description": match.group(2).strip(),
            "amount": float(match.group(3) or match.group(4)),
            "transaction_type": "debit" if match.group(3) else "credit"
        })
    
    return transactions


def parse_icici_statement(text: str) -> list:
    """Parse ICICI bank statement"""
    transactions = []
    # Similar pattern matching for ICICI
    pattern = r'(\d{2}-\w{3}-\d{4})\s+(.+?)\s+(INR)\s+(\d+\.\d{2})\s+(Dr|Cr)'
    
    for match in re.finditer(pattern, text):
        transactions.append({
            "date": match.group(1),
            "description": match.group(2).strip(),
            "amount": float(match.group(4)),
            "transaction_type": "debit" if match.group(5) == "Dr" else "credit"
        })
    
    return transactions


def parse_sbi_statement(text: str) -> list:
    """Parse SBI bank statement"""
    transactions = []
    # Pattern for SBI
    pattern = r'(\d{2}/\d{2})\s+(.+?)\s+(\d+\.\d{2})'
    
    for match in re.finditer(pattern, text):
        transactions.append({
            "date": match.group(1),
            "description": match.group(2).strip(),
            "amount": float(match.group(3)),
            "transaction_type": "debit"
        })
    
    return transactions


def parse_generic_statement(text: str) -> list:
    """Parse generic bank statement"""
    transactions = []
    # Generic pattern for amount detection
    amount_pattern = r'(\d+\.\d{2})'
    amounts = re.findall(amount_pattern, text)
    
    # Basic parsing
    for i, amount in enumerate(amounts[:10]):  # Limit to 10 transactions
        transactions.append({
            "date": str(datetime.utcnow().date()),
            "description": f"Transaction {i+1}",
            "amount": float(amount),
            "transaction_type": "debit"
        })
    
    return transactions

