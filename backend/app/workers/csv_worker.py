# from celery import shared_task  # Commented out for MVP - using direct calls
import pandas as pd
import io
from app.database.mongodb import get_mongo_db
from app.database.postgresql import SessionLocal
from app.models.spendsense_models import UploadBatch, TxnStaging
from datetime import datetime, date
from decimal import Decimal
import uuid


# @shared_task(name="parse_csv")  # Commented out for MVP - using direct calls
def parse_csv(user_id: str, source_id: str, file_content: bytes):
    """
    Parse CSV files and load to spendsense.txn_staging
    
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
        
        # Read CSV (as strings to avoid type coercion issues)
        # Try to detect if there are header rows before the actual column headers
        df_raw = pd.read_csv(io.BytesIO(file_content), dtype=str, header=None)
        
        # Find the row that contains transaction column headers (Date, Narration, etc.)
        header_row_idx = None
        for idx in range(min(25, len(df_raw))):  # Check first 25 rows
            row_values = [str(val).lower().strip() for val in df_raw.iloc[idx].values if pd.notna(val)]
            # Check if this row contains HDFC transaction column names
            has_date = any("date" in val for val in row_values)
            has_narration = any("narration" in val for val in row_values)
            has_withdrawal = any("withdrawal" in val for val in row_values)
            has_deposit = any("deposit" in val for val in row_values)
            
            if has_date and (has_narration or (has_withdrawal and has_deposit)):
                header_row_idx = idx
                print(f"📋 Found header row at index {idx}")
                break
        
        # Re-read CSV with correct header row
        if header_row_idx is not None and header_row_idx > 0:
            # Need to skip rows before header_row_idx, then use header_row_idx as header
            skip_rows = list(range(header_row_idx))
            df = pd.read_csv(io.BytesIO(file_content), dtype=str, skiprows=skip_rows, header=0).fillna("")
            print(f"⏭️  Skipped {header_row_idx} header rows")
        else:
            df = pd.read_csv(io.BytesIO(file_content), dtype=str).fillna("")
        
        # Remove rows where all values are empty or NaN
        df = df.dropna(how='all')
        
        # Log detected columns for debugging
        print(f"📋 Detected CSV columns: {list(df.columns)}")
        print(f"📊 Total rows in CSV: {len(df)}")
        print(f"📋 First few rows:\n{df.head()}")
        print(f"📋 Sample row values:\n{df.iloc[0] if len(df) > 0 else 'No rows'}")
        
        # Create upload batch in PostgreSQL (spendsense.upload_batch)
        upload_batch = UploadBatch(
            upload_id=uuid.uuid4(),
            user_id=uuid.UUID(user_id),
            source_type='file',
            file_name=file_name,
            total_records=len(df),
            parsed_records=0,
            status='received'
        )
        session.add(upload_batch)
        session.commit()
        
        upload_id = upload_batch.upload_id
        
        # Common column mappings for Indian banks
        column_mappings = {
            # Date
            "date": [
                "txn_date", "date", "transaction_date", "date_time", "transaction_dt", "value dt", "value_dt"
            ],
            # Descriptions
            "description": [
                "description_raw", "description", "narration", "particulars", "remarks"
            ],
            # Amount (single column format)
            "amount": [
                "amount", "transaction_amount", "amt"
            ],
            # HDFC-specific: Withdrawal and Deposit columns
            "withdrawal": [
                "withdrawal amt.", "withdrawal_amt", "withdrawal", "debit", "withdrawal amount"
            ],
            "deposit": [
                "deposit amt.", "deposit_amt", "deposit", "credit", "deposit amount"
            ],
            # Direction / Type
            "type": [
                "direction", "type", "transaction_type", "cr_dr", "debit_credit"
            ],
            # Merchant
            "merchant": [
                "merchant_raw", "merchant", "merchant_name", "payee"
            ],
            # Reference / Raw Txn Id
            "reference": [
                "raw_txn_id", "reference", "reference_id", "ref_no", "txn_id", "chq./ref.no.", "chq/ref no"
            ],
            # Currency
            "currency": [
                "currency", "curr"
            ],
            # Account reference
            "account_ref": [
                "account_ref", "account", "account_number"
            ],
            # User id (optional; usually taken from auth)
            "user_id": [
                "user_id", "uid"
            ]
        }
        
        # Find actual columns
        actual_cols = {}
        df_columns_lower = [col.lower().strip() for col in df.columns]
        
        for key, possible_names in column_mappings.items():
            for name in possible_names:
                name_lower = name.lower().strip()
                # Check if any column matches (case-insensitive, after stripping)
                matching_cols = [col for col in df.columns if col.lower().strip() == name_lower]
                if matching_cols:
                    actual_cols[key] = matching_cols[0]  # Take first match
                    print(f"✅ Mapped column '{key}' → '{actual_cols[key]}'")
                    break
        
        # Log all mapped columns
        print(f"📋 Column mappings found: {actual_cols}")
        
        staged_count = 0
        errors = []
        
        # Parse and stage transactions to spendsense.txn_staging
        for idx, row in df.iterrows():
            try:
                # Parse date - handle multiple formats including HDFC DD/MM/YY
                date_col = actual_cols.get("date")
                if not date_col:
                    # Try to find any column with "date" in the name
                    date_col = next((col for col in df.columns if "date" in col.lower()), None)
                
                date_str = str(row.get(date_col, "") if date_col else "")
                if not date_str or date_str.strip() == "" or date_str.lower() == "nan":
                    # Try alternative date columns for HDFC
                    for alt_col in ["Value Dt", "Value Dt.", "Value_Dt", "ValueDt"]:
                        if alt_col in df.columns:
                            date_str = str(row.get(alt_col, ""))
                            if date_str and date_str.strip() != "" and date_str.lower() != "nan":
                                break
                
                txn_date = None
                if date_str and date_str.strip() != "" and date_str.lower() != "nan":
                    # Try multiple date formats (4-digit year first)
                    for fmt in ['%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y', '%Y/%m/%d', '%d.%m.%Y', '%Y.%m.%d']:
                        try:
                            txn_date = datetime.strptime(date_str.strip(), fmt).date()
                            break
                        except:
                            continue
                    
                    # If still not parsed, try 2-digit year formats (HDFC uses DD/MM/YY)
                    if not txn_date:
                        for fmt in ['%d/%m/%y', '%d-%m-%y', '%d.%m.%y']:
                            try:
                                parsed_date = datetime.strptime(date_str.strip(), fmt).date()
                                # Convert 2-digit year to 4-digit (assume 20xx for years < 50, 19xx otherwise)
                                if parsed_date.year < 2000:
                                    if parsed_date.year < 50:
                                        txn_date = parsed_date.replace(year=2000 + parsed_date.year)
                                    else:
                                        txn_date = parsed_date.replace(year=1900 + parsed_date.year)
                                else:
                                    txn_date = parsed_date
                                break
                            except:
                                continue
                
                if not txn_date:
                    txn_date = date.today()
                
                # Parse amount - handle HDFC format with separate withdrawal/deposit columns
                direction = 'debit'  # default
                amount = Decimal('0')
                
                # Check for HDFC-style separate withdrawal and deposit columns
                withdrawal_col = actual_cols.get("withdrawal")
                deposit_col = actual_cols.get("deposit")
                
                # Also try to find these columns if not mapped
                if not withdrawal_col:
                    withdrawal_col = next((col for col in df.columns if "withdrawal" in col.lower()), None)
                if not deposit_col:
                    deposit_col = next((col for col in df.columns if "deposit" in col.lower()), None)
                
                print(f"🔍 Row {idx}: withdrawal_col={withdrawal_col}, deposit_col={deposit_col}")
                
                if withdrawal_col and deposit_col:
                    # HDFC format: separate withdrawal and deposit columns
                    withdrawal_val = row.get(withdrawal_col, "") if withdrawal_col else ""
                    deposit_val = row.get(deposit_col, "") if deposit_col else ""
                    
                    withdrawal_str = str(withdrawal_val) if withdrawal_val not in [None, "", "nan", "NaN"] else "0"
                    deposit_str = str(deposit_val) if deposit_val not in [None, "", "nan", "NaN"] else "0"
                    
                    # Clean and parse withdrawal
                    withdrawal_cleaned = withdrawal_str.replace(",", "").replace("₹", "").replace("Rs", "").replace("INR", "").strip()
                    if withdrawal_cleaned == "" or withdrawal_cleaned.lower() == "nan":
                        withdrawal_cleaned = "0"
                    try:
                        withdrawal_amt = Decimal(str(float(withdrawal_cleaned))) if withdrawal_cleaned and withdrawal_cleaned != "0" else Decimal('0')
                    except:
                        withdrawal_amt = Decimal('0')
                    
                    # Clean and parse deposit
                    deposit_cleaned = deposit_str.replace(",", "").replace("₹", "").replace("Rs", "").replace("INR", "").strip()
                    if deposit_cleaned == "" or deposit_cleaned.lower() == "nan":
                        deposit_cleaned = "0"
                    try:
                        deposit_amt = Decimal(str(float(deposit_cleaned))) if deposit_cleaned and deposit_cleaned != "0" else Decimal('0')
                    except:
                        deposit_amt = Decimal('0')
                    
                    print(f"💰 Row {idx}: withdrawal={withdrawal_amt}, deposit={deposit_amt}")
                    
                    # Determine direction and amount
                    if withdrawal_amt > 0 and deposit_amt == 0:
                        direction = 'debit'
                        amount = withdrawal_amt
                    elif deposit_amt > 0 and withdrawal_amt == 0:
                        direction = 'credit'
                        amount = deposit_amt
                    elif withdrawal_amt > 0 and deposit_amt > 0:
                        # Both have values (shouldn't happen, but handle it)
                        # Use the larger one or default to withdrawal
                        if withdrawal_amt >= deposit_amt:
                            direction = 'debit'
                            amount = withdrawal_amt
                        else:
                            direction = 'credit'
                            amount = deposit_amt
                    else:
                        # Both are zero - skip this row
                        continue
                else:
                    # Standard format: single amount column + direction
                    amount_str = str(row.get(actual_cols.get("amount", "amount"), "0"))
                    cleaned = amount_str.replace(",", "").replace("₹", "").replace("Rs", "").replace("INR", "").strip()
                    if cleaned == "":
                        cleaned = "0"
                    amount = Decimal(str(float(cleaned)))
                    
                    # Determine direction from type column
                    txn_type = str(row.get(actual_cols.get("type", "type"), "")).lower()
                    if 'credit' in txn_type or 'cr' in txn_type:
                        direction = 'credit'
                    elif amount < 0:
                        direction = 'debit'
                        amount = abs(amount)  # Store positive amount
                    elif amount > 0 and 'debit' in txn_type:
                        direction = 'debit'
                
                # Get description
                desc_col = actual_cols.get("description")
                if not desc_col:
                    # Try to find "narration" column
                    desc_col = next((col for col in df.columns if "narration" in col.lower()), None)
                
                description = "Unknown"
                if desc_col:
                    desc_val = row.get(desc_col, "")
                    description = str(desc_val).strip() if desc_val not in [None, "", "nan", "NaN"] else "Unknown"
                
                # Skip rows where amount is zero (both withdrawal and deposit are zero)
                if amount == Decimal('0'):
                    print(f"⏭️  Skipping row {idx}: amount is zero")
                    continue
                
                # Skip rows with invalid dates (future dates far in the future, or dates in 1900s)
                if txn_date.year > 2050 or txn_date.year < 2000:
                    print(f"⏭️  Skipping row {idx}: invalid date {txn_date}")
                    continue
                
                print(f"📝 Row {idx}: date={txn_date}, description={description[:50]}, amount={amount}, direction={direction}")

                # Optional fields
                currency = str(row.get(actual_cols.get("currency", "currency"), "")).strip() or 'INR'
                merchant_val = str(row.get(actual_cols.get("merchant", "merchant"), "")).strip() or None
                account_ref = str(row.get(actual_cols.get("account_ref", "account_ref"), "")).strip() or None
                raw_txn_id = str(row.get(actual_cols.get("reference", "reference"), "")).strip() or None
                
                # Extract merchant name from description if merchant_val is not provided or unclear
                # This handles UPI transactions like "UPI-MERCHANT-..." format
                if not merchant_val or merchant_val.lower() in ['unknown', 'nan', '']:
                    from app.services.merchant_extractor import extract_merchant_from_description
                    extracted_merchant = extract_merchant_from_description(description)
                    if extracted_merchant:
                        merchant_val = extracted_merchant
                
                # Create staging record
                staged_txn = TxnStaging(
                    upload_id=upload_id,
                    user_id=uuid.UUID(user_id),
                    raw_txn_id=raw_txn_id,
                    txn_date=txn_date,
                    description_raw=description,
                    amount=amount,
                    direction=direction,  # 'debit' = expense (withdrawal), 'credit' = income (deposit)
                    currency=currency,
                    merchant_raw=merchant_val,
                    account_ref=account_ref,
                    parsed_ok=True
                )
                session.add(staged_txn)
                staged_count += 1
                
            except Exception as e:
                errors.append(f"Row {idx+1}: {str(e)}")
        
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
            "errors": errors[:10]  # Return first 10 errors
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

