"""
ETL Pipeline API Endpoints
Exposes Extract, Transform, Load operations
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Request
from typing import List, Dict, Any, Optional, Tuple
import uuid
import os
import logging
from app.routers.auth import get_current_user, UserDep
from app.services.etl_pipeline import ETLPipeline
from app.routers._upload_utils import save_upload_to_temp, ensure_csv_mime, ensure_excel_mime
from app.routers._async_tools import run_sync
from app.schemas.etl import StagedTxnIn
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger(__name__)


class BatchStatusResponse(BaseModel):
    batch_id: str
    status: str
    total_records: int
    valid: int
    invalid: int
    processed: int
    failed: int


class ETLResponse(BaseModel):
    message: str
    batch_id: str
    records_staged: int


def _dispatch_or_fallback(parse_task, *, user_id: str, batch_id: str, file_name: str, path: str) -> ETLResponse:
    """
    Try Celery dispatch; if not available, fall back to threaded local parse.
    
    Returns ETLResponse with processing status.
    """
    try:
        if parse_task and hasattr(parse_task, "delay"):
            # Read file content for worker (workers currently expect bytes)
            with open(path, "rb") as f:
                file_bytes = f.read()
            
            parse_task.delay(
                user_id=str(user_id),
                source_id=str(batch_id),
                file_content=file_bytes  # Workers expect file_content: bytes
            )
            logger.info(f"Dispatched CSV/XLSX processing to worker for batch {batch_id}")
            return ETLResponse(
                message="File received. Processing in background.",
                batch_id=str(batch_id),
                records_staged=0
            )
    except Exception as e:
        logger.warning(f"Worker dispatch failed, falling back to sync processing: {e}")
        pass
    
    # Fallback: parse in-process on a thread
    try:
        # Defer heavy work to sync function
        if file_name.lower().endswith(".csv"):
            staged = _sync_parse_and_stage_csv
        else:
            staged = _sync_parse_and_stage_excel
        
        records_staged, valid, invalid = staged(user_id, batch_id, file_name, path)
        
        return ETLResponse(
            message=f"Upload processed: {valid} valid, {invalid} invalid",
            batch_id=str(batch_id),
            records_staged=records_staged,
        )
    finally:
        # Cleanup temp file on fallback completion
        try:
            os.remove(path)
        except Exception:
            pass


def _sync_parse_and_stage_csv(user_id: str, batch_id: str, file_name: str, path: str) -> Tuple[int, int, int]:
    """Synchronous CSV parsing and staging (runs in thread pool)"""
    import pandas as pd
    pipeline = ETLPipeline(user_id)
    
    try:
        df = pd.read_csv(path)
        txns = []
        
        for idx, row in df.iterrows():
            try:
                tx = StagedTxnIn(
                    amount=row.get("amount"),
                    transaction_date=row.get("date") or row.get("transaction_date"),
                    description=row.get("description") or row.get("narration"),
                    merchant=row.get("merchant"),
                    bank=row.get("bank"),
                    category=row.get("category"),
                    reference_id=row.get("reference") or row.get("reference_id"),
                    currency=row.get("currency", "INR"),
                    transaction_type=row.get("type") or row.get("transaction_type"),
                    source="csv",
                    row_number=idx + 1,
                )
                txns.append(tx.dict())
            except Exception as e:
                logger.warning(f"Skipping invalid row {idx + 1}: {e}")
                continue
        
        pipeline.stage_transactions(txns, batch_id)
        v = pipeline.validate_staged_transactions(batch_id)
        
        if v.get("valid", 0) > 0:
            pipeline.categorize_staged_transactions(batch_id)
            pipeline.load_to_production(batch_id)
        
        return len(txns), v.get("valid", 0), v.get("invalid", 0)
    except Exception as e:
        logger.exception(f"Error parsing CSV for batch {batch_id}")
        raise


def _sync_parse_and_stage_excel(user_id: str, batch_id: str, file_name: str, path: str) -> Tuple[int, int, int]:
    """Synchronous Excel parsing and staging (runs in thread pool)"""
    import pandas as pd
    pipeline = ETLPipeline(user_id)
    
    try:
        # Use openpyxl engine explicitly for .xlsx files
        df = pd.read_excel(path, engine="openpyxl")
        txns = []
        
        for idx, row in df.iterrows():
            try:
                tx = StagedTxnIn(
                    amount=row.get("amount"),
                    transaction_date=row.get("date") or row.get("transaction_date"),
                    description=row.get("description") or row.get("narration"),
                    merchant=row.get("merchant"),
                    bank=row.get("bank"),
                    category=row.get("category"),
                    reference_id=row.get("reference") or row.get("reference_id"),
                    currency=row.get("currency", "INR"),
                    transaction_type=row.get("type") or row.get("transaction_type"),
                    source="xlsx",
                    row_number=idx + 1,
                )
                txns.append(tx.dict())
            except Exception as e:
                logger.warning(f"Skipping invalid row {idx + 1}: {e}")
                continue
        
        pipeline.stage_transactions(txns, batch_id)
        v = pipeline.validate_staged_transactions(batch_id)
        
        if v.get("valid", 0) > 0:
            pipeline.categorize_staged_transactions(batch_id)
            pipeline.load_to_production(batch_id)
        
        return len(txns), v.get("valid", 0), v.get("invalid", 0)
    except Exception as e:
        logger.exception(f"Error parsing Excel for batch {batch_id}")
        raise


@router.post("/upload/csv", response_model=ETLResponse)
async def upload_csv_etl(
    file: UploadFile = File(...),
    user: UserDep = Depends(get_current_user)
):
    """
    Upload CSV file - Starts ETL pipeline (non-blocking)
    
    Process:
    1. Extract: Parse CSV and stage records (async worker)
    2. Transform: Validate and categorize (async worker)
    3. Load: Move to production tables (async worker)
    """
    # Stream to temp, sniff mime
    path, size, mime = await save_upload_to_temp(file)
    ensure_csv_mime(mime, file.filename)
    
    # Create upload batch
    pipeline = ETLPipeline(user.user_id)
    batch_id = pipeline.create_upload_batch(
        upload_type='csv',
        file_name=file.filename,
        file_size=size
    )
    
    logger.info(f"CSV upload batch created: {batch_id} for user {user.user_id}, size: {size}")
    
    # Try to get worker task
    try:
        from app.workers.csv_worker import parse_csv
    except Exception:
        parse_csv = None  # No worker available
    
    # Dispatch or fallback
    res = await run_sync(
        _dispatch_or_fallback,
        parse_csv,
        user_id=str(user.user_id),
        batch_id=str(batch_id),
        file_name=file.filename or "upload.csv",
        path=path
    )
    
    return res


@router.post("/upload/xlsx", response_model=ETLResponse)
async def upload_xlsx_etl(
    file: UploadFile = File(...),
    user: UserDep = Depends(get_current_user)
):
    """Upload XLSX file - Starts ETL pipeline (non-blocking)"""
    # Stream to temp, sniff mime
    path, size, mime = await save_upload_to_temp(file)
    kind = ensure_excel_mime(mime)  # "xlsx"|"xls"
    
    if kind == "xls":
        # Cleanup temp file before raising error
        try:
            os.remove(path)
        except Exception:
            pass
        raise HTTPException(status_code=400, detail="Legacy .xls not supported. Please upload .xlsx.")
    
    # Create upload batch
    pipeline = ETLPipeline(user.user_id)
    batch_id = pipeline.create_upload_batch(
        upload_type='xlsx',
        file_name=file.filename,
        file_size=size
    )
    
    logger.info(f"XLSX upload batch created: {batch_id} for user {user.user_id}, size: {size}")
    
    # Try to get worker task
    try:
        from app.workers.xls_worker import parse_xls
    except Exception:
        parse_xls = None  # No worker available
    
    # Dispatch or fallback
    res = await run_sync(
        _dispatch_or_fallback,
        parse_xls,
        user_id=str(user.user_id),
        batch_id=str(batch_id),
        file_name=file.filename or "upload.xlsx",
        path=path
    )
    
    return res


@router.get("/batches/{batch_id}", response_model=BatchStatusResponse)
async def get_batch_status(
    batch_id: str,
    user: UserDep = Depends(get_current_user)
):
    """Get status of upload batch"""
    pipeline = ETLPipeline(user.user_id)
    status_info = pipeline.get_batch_status(batch_id)
    
    if 'error' in status_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=status_info['error']
        )
    
    return status_info


@router.post("/batches/{batch_id}/validate")
async def validate_batch(
    batch_id: str,
    user: UserDep = Depends(get_current_user)
):
    """Manually trigger validation for a batch"""
    pipeline = ETLPipeline(user.user_id)
    result = pipeline.validate_staged_transactions(batch_id)
    
    return {
        "message": "Validation completed",
        "result": result
    }


@router.post("/batches/{batch_id}/categorize")
async def categorize_batch(
    batch_id: str,
    user: UserDep = Depends(get_current_user)
):
    """Manually trigger categorization for a batch"""
    pipeline = ETLPipeline(user.user_id)
    result = pipeline.categorize_staged_transactions(batch_id)
    
    return {
        "message": "Categorization completed",
        "result": result
    }


@router.post("/batches/{batch_id}/load")
async def load_batch(
    batch_id: str,
    user: UserDep = Depends(get_current_user)
):
    """Manually trigger loading to production"""
    pipeline = ETLPipeline(user.user_id)
    result = pipeline.load_to_production(batch_id)
    
    return {
        "message": "Load completed",
        "result": result
    }


@router.get("/batches")
async def list_batches(
    skip: int = 0,
    limit: int = 20,
    user: UserDep = Depends(get_current_user)
):
    """List all upload batches for user"""
    from app.database.postgresql import SessionLocal
    from app.models.staging_models import UploadBatch
    
    # Cap limit to prevent huge pulls
    limit = min(limit, 100)
    
    session = SessionLocal()
    try:
        batches = session.query(UploadBatch).filter(
            UploadBatch.user_id == user.user_id
        ).order_by(UploadBatch.created_at.desc()).offset(skip).limit(limit).all()
        
        return {
            "batches": [
                {
                    "id": batch.id,
                    "upload_type": batch.upload_type,
                    "file_name": batch.file_name,
                    "status": batch.status,
                    "total_records": batch.total_records,
                    "processed_records": batch.processed_records,
                    "created_at": batch.created_at.isoformat() if batch.created_at else None,
                    "completed_at": batch.completed_at.isoformat() if batch.completed_at else None
                }
                for batch in batches
            ]
        }
    finally:
        session.close()


# -----------------------------------------------------------------------------
# SpendSense: Direct load from staging -> fact + enrichment (MVP)
# -----------------------------------------------------------------------------
def load_staging_for_user(user_id_str: str) -> int:
    """Core loader: move staging rows for a user into fact + enrichment.

    Returns inserted count.
    """
    from app.database.postgresql import SessionLocal
    from app.models.spendsense_models import TxnStaging, TxnFact, TxnEnriched, DimCategory
    from sqlalchemy import text
    import uuid as _uuid

    def _extract_and_categorize(description: str, merchant_raw: Optional[str], direction: str) -> tuple:
        """
        Extract merchant name and categorize using merchant_rules.
        
        Returns:
            Tuple of (merchant_name_norm, category_code, subcategory_code)
        """
        from app.services.merchant_extractor import extract_merchant_from_description, normalize_merchant_name
        from app.services.pg_rules_client import PGRulesClient
        
        # Step 1: Extract merchant name from description if merchant_raw is not provided or unclear
        merchant_name = merchant_raw
        if not merchant_name or merchant_name.lower() in ['unknown', 'nan', '']:
            # Try to extract from description (for UPI transactions)
            merchant_name = extract_merchant_from_description(description or "")
        
        # Step 2: Normalize merchant name for matching
        merchant_normalized = normalize_merchant_name(merchant_name or description or "")
        
        # Step 3: Match against merchant_rules (user-specific + global)
        # Pass both merchant and description so rules can match either field
        rule_match = PGRulesClient.match_merchant(
            merchant_name=merchant_normalized or None,
            description=description or None,
            user_id=user_id_str,
            use_cache=True
        )
        
        if rule_match:
            # Only use the match if it has a category_code
            # Rules without categories (e.g., UPI pattern matchers) shouldn't stop further matching
            category_from_rule = rule_match.get("category_code")
            if category_from_rule:
                return (
                    rule_match.get("merchant_name_norm") or merchant_normalized,
                    category_from_rule,
                    rule_match.get("subcategory_code")
                )
            # If rule matched but has no category, continue to fallback
        
        # Step 4: Fallback to keyword-based inference
        if direction == 'credit':
            # Credits should NEVER be shopping/mobile_recharge/etc
            # Priority 1: Check if it's a personal name (2-4 words, no business keywords)
            search_text = (merchant_normalized or description or "").lower()
            words = search_text.split()
            is_personal_name = (len(words) >= 2 and len(words) <= 4 and 
                               not any(word in search_text for word in ["enterprises", "services", "solutions", "technologies", "private", "limited", "hotel", "hotels", "resort", "lodge", "industries", "trading", "traders", "store", "shop", "pvt", "ltd", "inc", "corp", "corporation"]))
            
            # Common Indian personal names
            common_names = ["abhinav", "shobha", "vasantha", "vasanthakumari", "yashwanth", "yashwant", "sriram", "kumari", "kiran", "uday", "navalga", "jatavath", "shaik", "zuber", "mohammad", "mohammed", "sameer", "shakeel", "arifa", "begum", "gurajala", "josaf", "pathlavath", "ramesh", "pittala", "yadagiri", "ippalui", "krishnaiah", "sandeep", "venkata", "hanuman", "naseer", "malla", "satya", "srinivasa", "ravi", "sri", "sai", "teja", "industr"]
            
            if is_personal_name or any(name in search_text for name in common_names):
                # Personal name → transfers
                return (merchant_normalized, "transfers", "p2p_transfer")
            
            # Priority 2: Check if merchant name looks like a company
            merchant_lower = (merchant_normalized or "").lower()
            company_keywords = ["technologies", "technology", "private", "limited", "pvt", "ltd", "inc", "corporation", "corp", "industries", "clearing", "nse", "bse", "nsec"]
            if any(keyword in merchant_lower for keyword in company_keywords):
                return (merchant_normalized, "income", "salary")
            
            # Priority 3: Check if it contains business keywords (but not personal name)
            business_keywords = ["enterprises", "services", "solutions", "traders", "store", "shop"]
            if any(word in merchant_lower for word in business_keywords):
                # Could be business payment → transfers or salary_income
                # If it's a small business, likely a transfer
                return (merchant_normalized, "transfers", "p2p_personal")
            
            # Default: credits from unknown sources → transfers (not salary_income)
            # This handles cases where we can't determine if it's personal or company
            return (merchant_normalized, "transfers", "p2p_personal")
        
        # For debits, use keyword matching
        search_text = (merchant_normalized or description or "").lower()
        category = _infer_category_from_keywords(search_text)
        
        return (merchant_normalized, category, None)
    
    def _infer_category_from_keywords(text: str) -> str:
        """Infer category from keywords (fallback for debits only) - uses India-first categories"""
        if not text:
            return "shopping"  # Default fallback (closest to "others")
        
        text_lower = text.lower()
        
        # New India-first taxonomy (13 categories)
        
        # Nightlife & Eating Out
        if any(k in text_lower for k in ["zomato", "swiggy", "food delivery"]):
            return "nightlife"  # food_delivery subcategory
        if any(k in text_lower for k in ["dine", "restaurant", "truffles", "food", "meal", "pizza", "burger"]):
            return "nightlife"  # restaurant_dineout subcategory
        if any(k in text_lower for k in ["cafe", "coffee", "cup", "theory", "barista"]):
            return "nightlife"  # coffee_cafe subcategory
        if any(k in text_lower for k in ["pub", "bar", "club", "lounge", "party", "event"]):
            return "nightlife"  # pub_bar or party_event subcategory
        if any(k in text_lower for k in ["pan", "paan", "beeda", "cigarette"]):
            return "nightlife"  # pan_shop subcategory
        
        # Home & Daily Needs
        if any(k in text_lower for k in ["bigbasket", "blinkit", "zepto", "dmart", "supermarket", "grocery", "kirana", "provisions"]):
            return "home_needs"  # groceries subcategory
        if any(k in text_lower for k in ["bescom", "bwssb", "tsspdcl", "electricity", "power"]):
            return "home_needs"  # electricity_home subcategory
        if any(k in text_lower for k in ["water", "water bill"]):
            return "home_needs"  # waterbill_home subcategory
        if any(k in text_lower for k in ["lpg", "gas", "cylinder"]):
            return "home_needs"  # gas_lpg subcategory
        if any(k in text_lower for k in ["apartment", "rent", "society", "maintenance", "property", "house", "flat"]):
            return "home_needs"  # rent_home or maintenance_society subcategory
        
        # Transport & Travel
        if any(k in text_lower for k in ["uber", "ola", "rapido", "cab", "taxi", "ride"]):
            return "transport"  # cab_ride subcategory
        if any(k in text_lower for k in ["auto", "rickshaw"]):
            return "transport"  # auto_rickshaw subcategory
        if any(k in text_lower for k in ["metro", "bus", "train", "irctc", "railways"]):
            return "transport"  # bus_train subcategory
        if any(k in text_lower for k in ["indigo", "vistara", "air india", "akasa", "flight", "airline"]):
            return "transport"  # flight subcategory
        if any(k in text_lower for k in ["hotel", "hotels", "resort", "lodge", "inn", "accommodation", "taj", "oberoi", "itc", "hilton", "marriott", "hyatt", "oyo", "booking", "stay"]):
            return "transport"  # hotel_stay subcategory
        if any(k in text_lower for k in ["fuel", "petrol", "diesel"]):
            return "transport"  # fuel_petrol subcategory
        if any(k in text_lower for k in ["fastag", "toll", "nhai", "parking"]):
            return "transport"  # toll_fastag or parking subcategory
        
        # Shopping & Lifestyle
        if any(k in text_lower for k in ["amazon", "flipkart", "myntra", "ajio", "meesho"]):
            return "shopping"  # online_shopping subcategory
        if any(k in text_lower for k in ["croma", "reliance digital", "electronics", "gadget"]):
            return "shopping"  # electronics subcategory
        if any(k in text_lower for k in ["apparel", "clothing", "footwear", "shirt", "pant", "dress"]):
            return "shopping"  # apparel subcategory
        if any(k in text_lower for k in ["bazaar", "mall", "store", "shop"]):
            return "shopping"  # online_shopping subcategory (default)
        
        # Bills & Recharges
        if any(k in text_lower for k in ["jio", "airtel", "vi", "vodafone", "idea", "bsnl", "mobile", "recharge"]):
            return "bills"  # mobile_recharge subcategory
        if any(k in text_lower for k in ["broadband", "internet", "jiofiber", "act", "hathway", "bsnl ftth"]):
            return "bills"  # broadband_internet subcategory
        if any(k in text_lower for k in ["tata play", "dth", "cable", "dishtv", "sun direct"]):
            return "bills"  # dth_cable subcategory
        if any(k in text_lower for k in ["credit card", "cc payment", "card payment", "card bill"]):
            return "bills"  # credit_card_due subcategory
        
        # Health & Wellness
        if any(k in text_lower for k in ["doctor", "hospital", "clinic", "consultation"]):
            return "health"  # hospital or doctor subcategory
        if any(k in text_lower for k in ["pharmacy", "medicine", "medplus", "apollo pharmacy"]):
            return "health"  # pharmacy subcategory
        if any(k in text_lower for k in ["diagnostics", "lab", "thyrocare", "lal path"]):
            return "health"  # diagnostics subcategory
        if any(k in text_lower for k in ["fitness", "gym", "yoga"]):
            return "health"  # fitness_gym subcategory
        
        # Loans & EMI
        if any(k in text_lower for k in ["loan", "emi", "personal loan", "home loan", "car loan"]):
            return "loans"  # loan_personal or loan_home subcategory
        
        # Insurance
        if any(k in text_lower for k in ["lic", "hdfc life", "sbi life", "insurance", "life insurance"]):
            return "insurance"  # insurance_life subcategory
        
        # Banking & Savings
        if any(k in text_lower for k in ["hdfc rd", "rd ", "recurring deposit", "hdfc mf", "index fund", "sip", "mutual fund", "investment", "stocks", "shares", "ppf", "fd", "fixed deposit"]):
            return "banks"  # bank_savings subcategory
        
        # Government & Taxes
        if any(k in text_lower for k in ["income tax", "tds", "advance tax", "gst", "property tax"]):
            return "govt_tax"  # income_tax or gst subcategory
        if any(k in text_lower for k in ["traffic", "fine", "challan"]):
            return "govt_tax"  # traffic_fine subcategory
        # Travel / Hotels (but exclude if it looks like a personal name)
        # Check if it's a personal name first (2-3 words, no business keywords)
        words = text_lower.split()
        is_personal_name = (len(words) >= 2 and len(words) <= 4 and 
                           not any(word in text_lower for word in ["enterprises", "services", "solutions", "technologies", "private", "limited", "hotel", "hotels", "resort", "lodge"]))
        
        if is_personal_name:
            # Likely a personal transfer - check common names
            common_names = ["abhinav", "shobha", "vasantha", "vasanthakumari", "yashwanth", "yashwant", "sriram", "kumari", "kiran", "uday", "navalga", "jatavath", "shaik", "zuber", "mohammad", "mohammed", "sameer", "shakeel", "arifa", "begum", "gurajala", "josaf", "pathlavath", "ramesh", "pittala", "yadagiri", "ippalui", "krishnaiah", "sandeep", "venkata", "hanuman", "naseer", "malla"]
            if any(name in text_lower for name in common_names):
                return "transfers"  # Personal transfer
        
        # Travel / Hotels (only if not a personal name)
        if not is_personal_name and any(k in text_lower for k in ["hotel", "hotels", "resort", "lodge", "inn", "accommodation", "taj", "oberoi", "itc", "hilton", "marriott", "hyatt", "oyo", "booking", "stay"]):
            return "travel"
        
        # Credit card apps / payments → bills.credit_card_due
        if any(k in text_lower for k in ["cred", "american express", "amex", "credit card", "cc payment", "card payment"]):
            return "bills"  # credit_card_due subcategory
        
        # Personal transfers/UPI to individuals - check if it looks like a business
        if any(k in text_lower for k in ["upi", "imps", "neft", "rtgs"]):
            # For personal names in UPI, check if it looks like a business
            business_keywords = ["enterprises", "services", "solutions", "traders", "store", "shop", "packages", "industries", "trading", "technologies", "private", "limited", "pvt", "ltd"]
            if any(word in text_lower for word in business_keywords):
                return "shopping"  # Likely a small business
            # Check if it's a company name (contains TECHNOLOGIES, PRIVATE, LIMITED, etc.)
            company_keywords = ["technologies", "technology", "private", "limited", "pvt", "ltd"]
            if any(word in text_lower for word in company_keywords):
                # Could be salary source - but if it's a debit, it's likely a payment to company
                return "shopping"
            # Personal transfer - check if it looks like a name
            if is_personal_name:
                return "transfers"
            # Default for UPI without clear merchant → transfers
            return "transfers"
        
        return "shopping"  # Default fallback (closest to "others")

    session = SessionLocal()
    inserted = 0
    try:
        user_id = _uuid.UUID(user_id_str) if isinstance(user_id_str, str) else user_id_str
        rows = session.query(TxnStaging).filter(
            TxnStaging.user_id == user_id,
            TxnStaging.parsed_ok == True
        ).all()

        # Ensure minimal categories exist for enrichment
        def ensure_category(cat_code: str):
            if not cat_code:
                return
            exists = session.query(DimCategory).filter(DimCategory.category_code == cat_code).first()
            if exists:
                return
            # Map to a txn_type bucket (using actual category codes from database)
            txn_type_map = {
                'dining': 'wants',
                'groceries': 'needs',
                'shopping': 'wants',
                'utilities': 'needs',
                'auto_taxi': 'needs',
                'flight': 'wants',
                'train': 'needs',
                'travel': 'wants',
                'rent': 'needs',
                'investments': 'assets',
                'income': 'income',
                'savings': 'assets',
                'others': 'wants'
            }
            txn_type = txn_type_map.get(cat_code, 'wants')
            # Format category name nicely (e.g., "auto_taxi" -> "Auto Taxi")
            category_name = cat_code.replace('_', ' ').title()
            session.add(DimCategory(category_code=cat_code, category_name=category_name, txn_type=txn_type, display_order=100, active=True))
            session.flush()

        for s in rows:
            # Extract merchant name and categorize using merchant_rules
            merchant_norm, category_code, subcategory_code = _extract_and_categorize(
                description=s.description_raw or "",
                merchant_raw=s.merchant_raw,
                direction=s.direction
            )
            
            # Calculate dedupe fingerprint once
            from sqlalchemy import text
            dedupe_fp_result = session.execute(text("""
                SELECT spendsense.fn_txn_fact_fp(:u, :d, :a, :dir, :desc, :m, :acct)
            """), {
                "u": s.user_id,
                "d": s.txn_date,
                "a": s.amount,
                "dir": s.direction,
                "desc": s.description_raw or "",
                "m": merchant_norm or "",
                "acct": getattr(s, 'account_ref', None) or ""
            }).scalar()
            
            # Check if transaction already exists using fingerprint
            existing = session.execute(text("""
                SELECT txn_id FROM spendsense.txn_fact
                WHERE dedupe_fp = :fp
                LIMIT 1
            """), {"fp": dedupe_fp_result}).first()
            
            if existing:
                # Transaction already exists - skip it
                continue
            
            # Use savepoint to isolate each transaction insert
            savepoint = session.begin_nested()
            try:
                fact = TxnFact(
                    user_id=s.user_id,
                    upload_id=s.upload_id,
                    source_type='file',
                    account_ref=getattr(s, 'account_ref', None),
                    txn_external_id=s.raw_txn_id,
                    txn_date=s.txn_date,
                    description=s.description_raw,
                    amount=s.amount,
                    direction=s.direction,  # 'debit' = expense, 'credit' = income
                    currency=s.currency or 'INR',
                    merchant_name_norm=merchant_norm or None
                )
                session.add(fact)
                session.flush()
                
                # Set audit fields via SQL (keeps model thin)
                session.execute(text("""
                    UPDATE spendsense.txn_fact
                    SET ingested_via = 'file',
                        raw_source_id = :upload_id
                    WHERE txn_id = :id
                """), {
                    "upload_id": s.upload_id,
                    "id": fact.txn_id
                })
                
                # Set dedupe_fp using already computed value (avoid recomputing)
                session.execute(text("""
                    UPDATE spendsense.txn_fact
                    SET dedupe_fp = :fp
                    WHERE txn_id = :id
                """), {
                    "fp": dedupe_fp_result,
                    "id": fact.txn_id
                })

                # Ensure category exists in dim_category to satisfy FK
                if category_code:
                    ensure_category(category_code)
                else:
                    # Fallback if no category found
                    category_code = "others"
                    ensure_category(category_code)
                
                # Create enriched record with category and subcategory
                enriched = TxnEnriched(
                    txn_id=fact.txn_id,
                    category_code=category_code,
                    subcategory_code=subcategory_code,
                    rule_confidence=1.0 if subcategory_code else 0.80
                )
                session.add(enriched)
                
                # Commit this individual transaction
                savepoint.commit()
                inserted += 1
            except Exception as insert_err:
                # Rollback just this savepoint (nested transaction)
                savepoint.rollback()
                
                # Handle duplicate key violations gracefully
                from sqlalchemy.exc import IntegrityError
                error_str = str(insert_err).lower()
                
                # Check if it's a duplicate/unique constraint violation
                is_duplicate = (
                    isinstance(insert_err, IntegrityError) or
                    ('unique' in error_str or 'duplicate' in error_str or 'ux_txn_fact_dedupe_fp' in error_str or 'dedupe_fp' in error_str)
                )
                
                if is_duplicate:
                    print(f"⚠️  Skipping duplicate transaction: {s.txn_date}, {s.amount}, {s.direction}")
                    # Continue to next transaction - savepoint rollback didn't affect other inserts
                    continue
                else:
                    # Some other error - re-raise it
                    raise

        # Commit all successful inserts at once
        session.commit()
        
        # Clear cache after loading to ensure fresh rules for next batch
        try:
            from app.services.pg_rules_client import clear_cache
            clear_cache()
        except Exception:
            pass  # Cache clearing is optional

        # Refresh KPIs for the user
        try:
            from app.routers.spendsense import _rebuild_kpis_for_user
            _rebuild_kpis_for_user(session, user_id_str)
            print(f"✅ KPIs refreshed for user {user_id_str}")
        except Exception as kpi_err:
            # Don't fail the whole operation if KPI refresh fails
            print(f"⚠️  Warning: Could not refresh KPIs: {kpi_err}")
        
        # Refresh materialized views if present
        try:
            # Check if views exist before refreshing
            result = session.execute(text("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_matviews 
                    WHERE schemaname = 'spendsense' 
                    AND matviewname = 'mv_spendsense_dashboard_user_month'
                )
            """))
            if result.scalar():
                try:
                    # Try CONCURRENTLY first (requires unique index)
                    session.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY spendsense.mv_spendsense_dashboard_user_month"))
                except Exception:
                    # Fallback to non-concurrent if no unique index
                    session.execute(text("REFRESH MATERIALIZED VIEW spendsense.mv_spendsense_dashboard_user_month"))
            
            result = session.execute(text("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_matviews 
                    WHERE schemaname = 'spendsense' 
                    AND matviewname = 'mv_spendsense_insights_user_month'
                )
            """))
            if result.scalar():
                try:
                    # Try CONCURRENTLY first (requires unique index)
                    session.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY spendsense.mv_spendsense_insights_user_month"))
                except Exception:
                    # Fallback to non-concurrent if no unique index
                    session.execute(text("REFRESH MATERIALIZED VIEW spendsense.mv_spendsense_insights_user_month"))
            
            session.commit()
        except Exception as mv_err:
            session.rollback()
            # Don't fail the whole operation if materialized view refresh fails
            print(f"⚠️  Warning: Could not refresh materialized views: {mv_err}")

        return inserted
    except Exception as e:
        session.rollback()
        logger.exception(f"Error in load_staging_for_user for user {user_id_str}")
        raise
    finally:
        session.close()


@router.post("/spendsense/load/staging")
async def spendsense_load_staging_to_fact(user: UserDep = Depends(get_current_user)):
    """API endpoint: move staging rows into fact + enrichment for the current user."""
    from app.database.postgresql import SessionLocal
    from app.models.spendsense_models import TxnStaging
    import uuid as _uuid
    try:
        # Quick visibility: how many staging rows do we have for this user?
        session = SessionLocal()
        user_id = _uuid.UUID(user.user_id) if isinstance(user.user_id, str) else user.user_id
        staging_count = session.query(TxnStaging).filter(TxnStaging.user_id == user_id).count()
        session.close()

        inserted = load_staging_for_user(user.user_id)
        return {"staging_count": staging_count, "inserted": inserted}
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        error_str = str(e).lower()
        
        # Log full error server-side
        logger.exception(f"Load staging error for user {user.user_id}: {e}")
        
        # Provide user-safe error messages (no tracebacks)
        if 'does not exist' in error_str or 'relation' in error_str or 'schema' in error_str:
            detail = "Database schema or tables do not exist. Please ensure the database is initialized."
        elif 'foreign key' in error_str or 'foreign_key' in error_str:
            detail = "Foreign key constraint violation. This usually means a category or merchant doesn't exist."
        elif 'unique constraint' in error_str or 'duplicate key' in error_str:
            detail = "Duplicate transaction detected."
        else:
            detail = "Load failed. Please try again or contact support with the batch ID."
        
        raise HTTPException(status_code=500, detail=detail)


@router.get("/spendsense/load/status")
async def spendsense_load_status(user: UserDep = Depends(get_current_user)):
    """Debug status for ETL counts per user (staging/fact)."""
    from app.database.postgresql import SessionLocal
    from app.models.spendsense_models import TxnStaging, TxnFact
    import uuid as _uuid

    session = SessionLocal()
    try:
        user_id = _uuid.UUID(user.user_id) if isinstance(user.user_id, str) else user.user_id
        staging_count = session.query(TxnStaging).filter(TxnStaging.user_id == user_id).count()
        fact_count = session.query(TxnFact).filter(TxnFact.user_id == user_id).count()
        return {"staging": staging_count, "fact": fact_count}
    finally:
        session.close()


@router.post("/spendsense/dev/run-all")
async def spendsense_dev_run_all(request: Request):
    """Development-only: load staging -> fact for all users with parsed rows.

    This endpoint is intentionally unprotected but only runs when
    settings.environment != 'production'. Useful when auth token is
    hard to provide from external tools.
    
    Security: Requires X-Internal-Token header and environment check.
    """
    from config import settings
    
    # Environment gate
    if getattr(settings, 'environment', 'development') == 'production':
        raise HTTPException(status_code=403, detail="Not allowed in production")
    
    # Internal token check
    internal_token = request.headers.get("X-Internal-Token")
    expected_token = getattr(settings, 'internal_token', 'dev-token-change-me')
    if internal_token != expected_token:
        raise HTTPException(status_code=403, detail="Invalid internal token")
    
    # IP allowlist (optional - can be configured)
    client_ip = request.client.host if request.client else None
    allowed_ips = getattr(settings, 'dev_allowed_ips', ['127.0.0.1', '::1', 'localhost'])
    if allowed_ips and client_ip not in allowed_ips:
        logger.warning(f"Blocked dev endpoint access from {client_ip}")
        raise HTTPException(status_code=403, detail="IP not allowed")

    from app.database.postgresql import SessionLocal
    from app.models.spendsense_models import TxnStaging
    from sqlalchemy import distinct

    session = SessionLocal()
    try:
        user_ids = [row[0] for row in session.query(distinct(TxnStaging.user_id)).filter(TxnStaging.parsed_ok == True).all()]
        total_inserted = 0
        details = []
        for uid in user_ids:
            try:
                inserted = load_staging_for_user(str(uid))
                total_inserted += inserted
                details.append({"user_id": str(uid), "inserted": inserted})
            except Exception as e:
                details.append({"user_id": str(uid), "error": str(e)})
        return {"users": len(user_ids), "inserted": total_inserted, "details": details}
    finally:
        session.close()

