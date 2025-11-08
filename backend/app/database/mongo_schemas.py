"""
MongoDB Schema Definitions for Raw → Parsed → Cleaned Pipeline

Collections:
1. raw_files - Binary file storage metadata
2. raw_events - One document per candidate transaction (raw row/line)
3. parsed_events - Structured parsed data before normalization
4. upload_jobs - Job tracking (existing, kept for backward compat)
"""

from datetime import datetime
from typing import Optional, Dict, Any
from pymongo import IndexModel, ASCENDING, DESCENDING, TEXT
import hashlib


# ============================================================================
# Collection: raw_files
# ============================================================================

def create_raw_files_collection(db):
    """Create and configure raw_files collection"""
    collection = db["raw_files"]
    
    # Create indexes
    indexes = [
        IndexModel([("user_id", ASCENDING), ("ingested_at", DESCENDING)]),
        IndexModel([("hash_sha256", ASCENDING)], unique=True, sparse=True),
        IndexModel([("job_id", ASCENDING)]),
        IndexModel([("status", ASCENDING)]),
    ]
    collection.create_indexes(indexes)
    
    return collection


def create_raw_file_document(
    user_id: str,
    source_type: str,  # "csv", "pdf", "email"
    file_name: str,
    file_content: bytes,
    content_type: str,
    job_id: str,
    storage_kind: str = "mongo",  # "mongo" or "s3"
    storage_url: Optional[str] = None,
    storage_etag: Optional[str] = None,
    bank_hint: Optional[str] = None,  # "HDFC", "SBI", "ICICI", "AXIS", etc.
    period_hint: Optional[Dict[str, int]] = None,  # {"month": 11, "year": 2025}
) -> Dict[str, Any]:
    """
    Create a raw_file document
    
    Args:
        user_id: User UUID
        source_type: "csv", "pdf", or "email"
        file_name: Original filename
        file_content: File bytes
        content_type: MIME type
        job_id: Upload job UUID
        storage_kind: "mongo" (store in GridFS) or "s3" (store URL)
        storage_url: S3 URL if storage_kind="s3"
        storage_etag: S3 ETag if applicable
        bank_hint: Bank identifier if detected (e.g., "HDFC", "SBI")
        period_hint: Period hint if detected (e.g., {"month": 11, "year": 2025})
    
    Returns:
        Document dictionary
    """
    # Compute SHA256 hash for deduplication
    hash_sha256 = hashlib.sha256(file_content).hexdigest()
    
    doc = {
        "schema_version": 1,
        "user_id": user_id,
        "source_type": source_type,
        "file_name": file_name,
        "content_type": content_type,
        "size_bytes": len(file_content),
        "storage": {
            "kind": storage_kind,
            "url": storage_url,
            "etag": storage_etag,
        },
        "ingested_at": datetime.utcnow(),
        "job_id": job_id,
        "hash_sha256": hash_sha256,
        "bank_hint": bank_hint or "unknown",
        "period_hint": period_hint,
        "status": "stored",  # "stored" → "parsed" → "error"
        "error": None,
    }
    
    # If storing in MongoDB GridFS, add gridfs_id after upload
    if storage_kind == "mongo":
        doc["storage"]["gridfs_id"] = None
    
    return doc


# ============================================================================
# Collection: raw_events
# ============================================================================

def create_raw_events_collection(db):
    """Create and configure raw_events collection"""
    collection = db["raw_events"]
    
    # Create indexes
    indexes = [
        IndexModel([("user_id", ASCENDING), ("status", ASCENDING), ("created_at", DESCENDING)]),
        IndexModel([("fingerprint", ASCENDING)], unique=True, sparse=True),
        IndexModel([("job_id", ASCENDING)]),
        IndexModel([("file_id", ASCENDING)]),
        IndexModel([("source_cursor.csv_row", ASCENDING)]),  # For CSV row lookup
        IndexModel([("source_cursor.email_id", ASCENDING)]),  # For email lookup
    ]
    collection.create_indexes(indexes)
    
    return collection


def create_raw_event_document(
    user_id: str,
    source_type: str,  # "csv", "pdf", "email"
    job_id: str,
    file_id: Optional[str] = None,  # ObjectId of raw_file
    csv_row: Optional[int] = None,
    email_id: Optional[str] = None,
    pdf_page: Optional[int] = None,
    line_no: Optional[int] = None,
    raw_text: Optional[str] = None,  # For PDF/Email
    raw_row: Optional[Dict[str, Any]] = None,  # For CSV
    account_hint: Optional[str] = None,  # Account identifier (last4, IBAN frag)
    pii_masked: bool = False,  # Whether PII has been masked
) -> Dict[str, Any]:
    """
    Create a raw_event document
    
    Args:
        user_id: User UUID
        source_type: "csv", "pdf", or "email"
        job_id: Upload job UUID
        file_id: MongoDB ObjectId of raw_file
        csv_row: Row number in CSV (0-indexed)
        email_id: Gmail message ID
        pdf_page: Page number in PDF
        line_no: Line number in PDF/email text
        raw_text: Full text line for PDF/Email
        raw_row: Dictionary of column values for CSV
    
    Returns:
        Document dictionary
    """
    # Build source_cursor
    source_cursor = {}
    if csv_row is not None:
        source_cursor["csv_row"] = csv_row
    if email_id is not None:
        source_cursor["email_id"] = email_id
    if pdf_page is not None:
        source_cursor["pdf_page"] = pdf_page
    if line_no is not None:
        source_cursor["line_no"] = line_no
    
    # Compute fingerprint for deduplication
    fingerprint_parts = [source_type]
    if file_id:
        fingerprint_parts.append(str(file_id))
    if email_id:
        fingerprint_parts.append(email_id)
    if csv_row is not None:
        fingerprint_parts.append(f"row:{csv_row}")
    if raw_row:
        fingerprint_parts.append(str(sorted(raw_row.items())))
    if raw_text:
        fingerprint_parts.append(raw_text[:100])  # First 100 chars for fingerprint
    
    fingerprint = hashlib.sha1("|".join(fingerprint_parts).encode()).hexdigest()
    
    doc = {
        "schema_version": 1,
        "user_id": user_id,
        "source_type": source_type,
        "file_id": file_id,
        "job_id": job_id,
        "source_cursor": source_cursor,
        "raw_text": raw_text,
        "raw_row": raw_row,
        "account_hint": account_hint,
        "created_at": datetime.utcnow(),
        "status": "ready",  # "ready" → "parsed" → "error"
        "error": None,
        "pii_masked": pii_masked,
        "fingerprint": fingerprint,
    }
    
    return doc


# ============================================================================
# Collection: parsed_events
# ============================================================================

def create_parsed_events_collection(db):
    """Create and configure parsed_events collection"""
    collection = db["parsed_events"]
    
    # Create indexes
    indexes = [
        IndexModel([("user_id", ASCENDING), ("status", ASCENDING)]),
        IndexModel([("dedupe_key", ASCENDING)], unique=True, sparse=True),
        IndexModel([("raw_event_id", ASCENDING)]),
        IndexModel([("job_id", ASCENDING)]),
        IndexModel([("parsed.date_str", ASCENDING)]),  # For date range queries
    ]
    collection.create_indexes(indexes)
    
    return collection


def create_parsed_event_document(
    user_id: str,
    raw_event_id: str,  # ObjectId of raw_event
    job_id: str,
    parsed: Dict[str, Any],  # Parsed fields (date_str, amount_str, merchant, etc.)
    normalized: Optional[Dict[str, Any]] = None,  # Optional normalized fields
    bank: Optional[str] = None,  # "HDFC", "SBI", "ICICI", "AXIS", "ANY"
    channel: Optional[str] = None,  # "sms", "email", "pdf", "csv", "any"
    rule_id: Optional[str] = None,  # UUID of parser_rule that matched
    rule_kind: str = "heuristic",  # "parser_rule" or "heuristic"
) -> Dict[str, Any]:
    """
    Create a parsed_event document
    
    Args:
        user_id: User UUID
        raw_event_id: MongoDB ObjectId of raw_event
        job_id: Upload job UUID
        parsed: Dictionary of parsed fields (date_str, amount_str, dc, merchant, upi, ref, etc.)
        normalized: Optional normalized fields (date, amount, balance)
    
    Returns:
        Document dictionary
    """
    # Compute dedupe_key for idempotency (include bank in key)
    dedupe_parts = [
        str(bank or "ANY"),
        str(parsed.get("date_str", "")),
        str(parsed.get("amount_str", "")),
        str(parsed.get("ref", "")),
        str(parsed.get("upi", "")),
        str(parsed.get("merchant", "")),
        str(parsed.get("account_hint", "")),
    ]
    dedupe_key = hashlib.sha1("|".join(dedupe_parts).encode()).hexdigest()
    
    doc = {
        "schema_version": 1,
        "user_id": user_id,
        "raw_event_id": raw_event_id,
        "job_id": job_id,
        "bank": bank or "ANY",
        "channel": channel or "any",
        "rule_id": rule_id,
        "rule_kind": rule_kind,
        "parsed": parsed,
        "normalized": normalized or {},
        "status": "parsed",  # "parsed" → "cleaned" → "exported" → "error"
        "error": None,
        "dedupe_key": dedupe_key,
        "created_at": datetime.utcnow(),
        "exported_at": None,  # Set when exported to PostgreSQL
        "pg_txn_ids": [],  # List of PostgreSQL txn_fact IDs after export
        "pg_upload_id": None,  # PostgreSQL upload_batch.upload_id
    }
    
    return doc


# ============================================================================
# Helper Functions
# ============================================================================

def initialize_mongo_collections(db):
    """Initialize all MongoDB collections with indexes"""
    print("📦 Initializing MongoDB collections...")
    
    collections = {
        "raw_files": create_raw_files_collection(db),
        "raw_events": create_raw_events_collection(db),
        "parsed_events": create_parsed_events_collection(db),
    }
    
    print(f"✅ Initialized {len(collections)} MongoDB collections")
    return collections


def compute_file_hash(file_content: bytes) -> str:
    """Compute SHA256 hash of file content"""
    return hashlib.sha256(file_content).hexdigest()


def compute_event_fingerprint(
    source_type: str,
    file_id: Optional[str] = None,
    email_id: Optional[str] = None,
    csv_row: Optional[int] = None,
    raw_content: Optional[str] = None,
) -> str:
    """Compute fingerprint for raw_event deduplication"""
    parts = [source_type]
    if file_id:
        parts.append(str(file_id))
    if email_id:
        parts.append(email_id)
    if csv_row is not None:
        parts.append(f"row:{csv_row}")
    if raw_content:
        parts.append(raw_content[:200])  # First 200 chars
    
    return hashlib.sha1("|".join(parts).encode()).hexdigest()


def compute_parsed_dedupe_key(
    date_str: str,
    amount_str: str,
    ref: str = "",
    upi: str = "",
    merchant: str = "",
    account_hint: str = "",
) -> str:
    """Compute dedupe_key for parsed_event"""
    parts = [
        str(date_str),
        str(amount_str),
        str(ref),
        str(upi),
        str(merchant),
        str(account_hint),
    ]
    return hashlib.sha1("|".join(parts).encode()).hexdigest()

