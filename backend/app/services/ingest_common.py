"""
Common utilities for Mongo-first ingestion
Fingerprinting and deduplication helpers
"""
import hashlib
from datetime import datetime


def fp_raw(user_id: str, email_id: str, piece: str) -> str:
    """
    Stable fingerprint per user + email + text block
    
    Args:
        user_id: User UUID string
        email_id: Email ID (Gmail message ID or similar)
        piece: Text content (subject + body or raw row)
    
    Returns:
        SHA1 hex digest fingerprint
    """
    h = hashlib.sha1()
    h.update(f"{user_id}|{email_id}|{piece}".encode("utf-8"))
    return h.hexdigest()


def dedupe_key_from_parsed(parsed: dict) -> str:
    """
    Robust transaction identity for deduplication
    
    Computes from: bank|date|amount|ref|upi|merchant|acct
    
    Args:
        parsed: Parsed transaction dict (from fn_parse_txn_line or similar)
    
    Returns:
        SHA1 hex digest dedupe key
    """
    bank = parsed.get("bank", "") or parsed.get("bank_hint", "") or ""
    date = parsed.get("date", "") or parsed.get("date_str", "") or ""
    amount = parsed.get("amount", "") or parsed.get("amount_str", "") or ""
    ref = parsed.get("ref", "") or parsed.get("reference", "") or ""
    upi = parsed.get("upi", "") or parsed.get("upi_id", "") or ""
    merch = parsed.get("merchant", "") or parsed.get("merchant_name", "") or ""
    acct = parsed.get("acct", "") or parsed.get("account_hint", "") or ""
    
    base = f"{bank}|{date}|{amount}|{ref}|{upi}|{merch}|{acct}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()


def fp_csv_raw(user_id: str, file_id: str, row_index: int, row_content: str) -> str:
    """
    Fingerprint for CSV raw events
    
    Args:
        user_id: User UUID string
        file_id: File/upload ID
        row_index: CSV row number (0-indexed)
        row_content: Raw row content (JSON stringified dict or CSV line)
    
    Returns:
        SHA1 hex digest fingerprint
    """
    h = hashlib.sha1()
    h.update(f"csv|{user_id}|{file_id}|{row_index}|{row_content}".encode("utf-8"))
    return h.hexdigest()


def fp_pdf_raw(user_id: str, file_id: str, page: int, line_no: int, line_text: str) -> str:
    """
    Fingerprint for PDF raw events
    
    Args:
        user_id: User UUID string
        file_id: File/upload ID
        page: PDF page number
        line_no: Line number within page
        line_text: Raw line text
    
    Returns:
        SHA1 hex digest fingerprint
    """
    h = hashlib.sha1()
    h.update(f"pdf|{user_id}|{file_id}|{page}|{line_no}|{line_text}".encode("utf-8"))
    return h.hexdigest()

