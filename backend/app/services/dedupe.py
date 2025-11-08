"""
Dedupe Service
Computes and checks dedupe_key for idempotency
"""

from typing import Dict, Any, Optional
import hashlib


class DedupeService:
    """Service for computing dedupe keys"""
    
    @staticmethod
    def compute_dedupe_key(
        bank: Optional[str] = None,
        date_str: Optional[str] = None,
        amount_str: Optional[str] = None,
        ref: Optional[str] = None,
        upi: Optional[str] = None,
        merchant: Optional[str] = None,
        account_hint: Optional[str] = None,
    ) -> str:
        """
        Compute dedupe_key for parsed_event
        
        Args:
            bank: Bank identifier
            date_str: Date string
            amount_str: Amount string
            ref: Reference number
            upi: UPI ID
            merchant: Merchant name
            account_hint: Account hint
        
        Returns:
            SHA1 hash of dedupe key
        """
        dedupe_parts = [
            str(bank or "ANY"),
            str(date_str or ""),
            str(amount_str or ""),
            str(ref or ""),
            str(upi or ""),
            str(merchant or ""),
            str(account_hint or ""),
        ]
        return hashlib.sha1("|".join(dedupe_parts).encode()).hexdigest()
    
    @staticmethod
    def compute_fingerprint(
        source_type: str,
        file_id: Optional[str] = None,
        email_id: Optional[str] = None,
        csv_row: Optional[int] = None,
        raw_content: Optional[str] = None,
    ) -> str:
        """
        Compute fingerprint for raw_event
        
        Args:
            source_type: Source type ("csv", "pdf", "email")
            file_id: File ObjectId
            email_id: Email ID
            csv_row: CSV row number
            raw_content: Raw content string
        
        Returns:
            SHA1 hash of fingerprint
        """
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

