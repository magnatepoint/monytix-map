"""
Merchant name extraction from UPI transaction descriptions
"""
import re
from typing import Optional


def extract_merchant_from_description(description: str) -> Optional[str]:
    """
    Extract merchant name from various transaction description formats.
    
    Handles formats like:
    - UPI: "UPI-ABHINAV ERRAPALLY-ABHINAV.ERRAPALLY-1@00000529566515591"
    - UPI: "UPI-SHAKEEL MOHAMMAD-9652063370@YBL-SBIN000000113060535138"
    - UPI: "REV-UPI-50100154236544-SANTOSH.MVHS@OKHDFCBANK-..."
    - ACH: "ACH D- NSECLEARINGLIMITED-3142768919"
    - ACH: "ACH D- RAZORPAYSOFTWAREPRIV-ADITYABIRLQF"
    - IB: "IB BILLPAY DR-HDFCCS-457262XXXXXX6844"
    - NEFT: "NEFT CR-IDFB0010204-MAGNATEPOINT TECHNOLOGIES PRIVATE L-VENKATA HANUMA"
    - Card: "BHDFU4F0H84OGQ/BILLDKHDFCCARD"
    - Card: "POS 416021XXXXXX1514 PZ HDFC CC BILLP"
    
    Returns:
        Extracted merchant name or None
    """
    if not description:
        return None
    
    desc_upper = description.upper()
    
    # Pattern 1: UPI transactions (standard format)
    # Format: UPI-MERCHANT_NAME-rest_of_string
    patterns = [
        # Format: UPI-MERCHANT-REST
        r'UPI-([A-Z][A-Z\s]+?)(?:-|@|$)',
        # Format: UPI-MERCHANT_NAME-MORE-REST
        r'UPI-([A-Z][A-Z\s]+?)-[A-Z0-9]',
        # Format: UPI-MERCHANT@...
        r'UPI-([A-Z][A-Z\s]+?)@',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, description, re.IGNORECASE)
        if match:
            merchant = match.group(1).strip()
            merchant = re.sub(r'\s+', ' ', merchant).strip()
            merchant = re.sub(r'-\d+$', '', merchant)
            if len(merchant) > 2:
                return merchant
    
    # Pattern 2: REV-UPI (Reversal/Refund UPI transactions)
    # Format: REV-UPI-...-MERCHANT@...
    if desc_upper.startswith('REV-UPI-'):
        # Try to extract from email format: ...-MERCHANT@...
        # Example: REV-UPI-50100154236544-SANTOSH.MVHS@OKHDFCBANK-...
        match = re.search(r'-([A-Z][A-Z0-9._]+)@', description, re.IGNORECASE)
        if match:
            merchant = match.group(1).strip()
            # Extract name part before . (if email format)
            merchant = merchant.split('.')[0] if '.' in merchant else merchant
            merchant = re.sub(r'\d+$', '', merchant).strip()
            if len(merchant) > 2:
                return merchant
    
    # Pattern 3: ACH transactions
    # Format: ACH D- MERCHANT-...
    if desc_upper.startswith('ACH D-') or desc_upper.startswith('ACH CR-'):
        parts = description.split('-', 2)
        if len(parts) >= 2:
            merchant = parts[1].strip()
            # Remove trailing numbers/IDs
            merchant = re.sub(r'-\d+$', '', merchant).strip()
            merchant = re.sub(r'\s+\d+$', '', merchant).strip()
            if len(merchant) > 2:
                return merchant
    
    # Pattern 4: IB BILLPAY (Internet Banking Bill Payments)
    # Format: IB BILLPAY DR-MERCHANT-...
    # Note: Often contains bank codes (HDFCCS, HDFC4W) which aren't merchants
    if 'BILLPAY' in desc_upper:
        # Skip if it's just a bank code pattern (4-6 uppercase letters/numbers)
        match = re.search(r'BILLPAY\s+(?:DR|CR)-([A-Z0-9]+)', description, re.IGNORECASE)
        if match:
            merchant = match.group(1).strip()
            # Skip if it looks like a bank code (HDFC, ICICI, etc.)
            bank_codes = ['HDFCCS', 'HDFC4W', 'ICICI', 'SBI', 'AXIS', 'KOTAK']
            if merchant.upper() not in bank_codes and len(merchant) > 2:
                return merchant
    
    # Pattern 5: NEFT transactions
    # Format: NEFT CR-IDFB0010204-MERCHANT NAME-...
    if desc_upper.startswith('NEFT '):
        parts = description.split('-')
        if len(parts) >= 3:
            # Skip first two parts (NEFT CR, bank code), get merchant name
            merchant = parts[2].strip()
            # Take only the first part if there are multiple (before next separator)
            merchant = merchant.split('-')[0].strip()
            merchant = merchant.split(' ')[:3]  # Take first 3 words (usually merchant name)
            merchant = ' '.join(merchant).strip()
            if len(merchant) > 2:
                return merchant
    
    # Pattern 6: HDFC Card payments
    # Format: BHDF.../BILLDK...
    # Format: POS ... HDFC CC ...
    # Format: BHDFU4F0H84OGQ/BILLDKHDFCCARD
    # Format: BHDFV8G0HT20Z9/BILLDKAMERICANEXPRES
    if '/' in description and ('BILLD' in desc_upper or 'HDFC' in desc_upper):
        parts = description.split('/')
        if len(parts) >= 2:
            merchant = parts[1].strip()
            # For formats like BILLDKAMERICANEXPRES, extract AMERICANEXPRES
            if 'BILLDK' in merchant.upper() and len(merchant) > 8:
                # Try to extract merchant name after BILLDK prefix
                merchant = re.sub(r'^BILLDK', '', merchant, flags=re.IGNORECASE).strip()
                # Remove common suffixes
                merchant = re.sub(r'(HDFC|CARD).*$', '', merchant, flags=re.IGNORECASE).strip()
                if len(merchant) > 2:
                    return merchant
            # Remove common card suffixes (BILLDK, HDFC, CARD, etc.)
            merchant = re.sub(r'BILLD[A-Z]+$', '', merchant, flags=re.IGNORECASE).strip()
            merchant = re.sub(r'HDFC.*$', '', merchant, flags=re.IGNORECASE).strip()
            merchant = re.sub(r'CARD.*$', '', merchant, flags=re.IGNORECASE).strip()
            if len(merchant) > 2:
                return merchant
    
    # Pattern 6b: Encoded merchant codes with RAZPDSP prefix
    # Format: QEC6ZIL2EXNX1Z/RAZPDSPFINANCEPRIVAT
    if '/' in description and 'RAZPDSP' in desc_upper:
        parts = description.split('/')
        if len(parts) >= 2:
            merchant = parts[1].strip()
            # Remove RAZPDSP prefix
            merchant = re.sub(r'^RAZPDSP', '', merchant, flags=re.IGNORECASE).strip()
            if len(merchant) > 2:
                return merchant
    
    # Pattern 6c: NWD (Net Banking Withdrawal)
    # Format: NWD-416021XXXXXX1514-4498WS01-KHAMMAM
    if desc_upper.startswith('NWD-'):
        parts = description.split('-')
        if len(parts) >= 3:
            # Last part is usually location/merchant
            merchant = parts[-1].strip()
            if len(merchant) > 2 and not merchant.isdigit():
                return merchant
    
    # Pattern 6d: IMPS transactions (person-to-person, often not merchants)
    # Format: IMPS-518508833581-KISETSUSAISONFINAN-UTIB-...
    # Format: IMPS-523319907137-MALLA VASANTHI-KKBK-...
    if desc_upper.startswith('IMPS-'):
        parts = description.split('-')
        if len(parts) >= 3:
            # Third part might be merchant/bank name
            merchant = parts[2].strip()
            # Skip if it looks like a bank code
            bank_codes = ['UTIB', 'KKBK', 'ICIC', 'HDFC', 'SBIN']
            if merchant.upper() not in bank_codes and len(merchant) > 2:
                return merchant
    
    # Pattern 7: Generic fallback - extract first meaningful word sequence
    # For descriptions like "POS ... MERCHANT ..."
    words = description.split()
    if len(words) > 2:
        # Try to find merchant-like patterns (capitalized words, 2+ chars)
        merchant_parts = []
        for word in words[1:5]:  # Check first few words after transaction type
            clean_word = re.sub(r'[^A-Za-z]', '', word)
            if len(clean_word) >= 2 and clean_word[0].isupper():
                merchant_parts.append(clean_word)
                if len(merchant_parts) >= 1:  # Got at least one meaningful word
                    merchant = ' '.join(merchant_parts).strip()
                    if len(merchant) > 2:
                        return merchant
    
    # Final fallback: If description starts with "UPI-" but doesn't match patterns
    if desc_upper.startswith('UPI-'):
        parts = description.split('-', 2)
        if len(parts) >= 2:
            potential_merchant = parts[1].strip()
            potential_merchant = re.sub(r'@.*$', '', potential_merchant)
            potential_merchant = re.sub(r'\d+$', '', potential_merchant).strip()
            if len(potential_merchant) > 2:
                return potential_merchant
    
    return None


def normalize_merchant_name(merchant: str) -> str:
    """
    Normalize merchant name for matching - aggressive normalization.
    
    - Uppercase
    - Remove punctuation (keep spaces and alphanumeric)
    - Remove extra spaces
    - Remove common suffixes/prefixes
    """
    if not merchant:
        return ""
    
    # Uppercase and clean spaces
    normalized = merchant.upper().strip()
    
    # Remove all punctuation except spaces (for better matching)
    # This helps match "SHOBA ENTERPRISES" with "SHOBA-ENTERPRISES" or "SHOBA.ENTERPRISES"
    normalized = re.sub(r'[^A-Z0-9\s]', '', normalized)
    
    # Normalize spaces
    normalized = re.sub(r'\s+', ' ', normalized)
    
    # Remove common prefixes
    normalized = re.sub(r'^(UPI|PAYTM|PHONEPE|GPAY)\s*', '', normalized, flags=re.IGNORECASE)
    
    # Remove trailing UPI IDs, numbers, etc.
    normalized = re.sub(r'\s+@\S+$', '', normalized)
    normalized = re.sub(r'\s+\d+$', '', normalized)
    
    return normalized.strip()

