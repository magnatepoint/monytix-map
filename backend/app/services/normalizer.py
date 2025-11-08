"""
Normalizer Service
Handles numeric parsing, date parsing (multi-format), sign rules, currency defaults
"""

from datetime import datetime, date
from decimal import Decimal
from typing import Optional, Dict, Any
import re


class Normalizer:
    """Service for normalizing parsed transaction data"""
    
    # Date format patterns (ordered by most common first)
    DATE_FORMATS = [
        '%Y-%m-%d',           # 2025-11-01
        '%d/%m/%Y',           # 01/11/2025
        '%d-%m-%Y',           # 01-11-2025
        '%d.%m.%Y',           # 01.11.2025
        '%d/%m/%y',           # 01/11/25 (2-digit year)
        '%d-%m-%y',           # 01-11-25
        '%d.%m.%y',           # 01.11.25
        '%Y/%m/%d',           # 2025/11/01
        '%m/%d/%Y',           # 11/01/2025 (US format)
        '%d %b %Y',           # 01 Nov 2025
        '%d %B %Y',           # 01 November 2025
    ]
    
    @staticmethod
    def parse_date(date_str: Optional[str]) -> Optional[date]:
        """
        Parse date string in multiple formats
        
        Args:
            date_str: Date string in various formats
        
        Returns:
            date object or None if unparseable
        """
        if not date_str or not isinstance(date_str, str):
            return None
        
        date_str = date_str.strip()
        if not date_str or date_str.lower() in ['nan', 'none', 'null', '']:
            return None
        
        # Try parsing with various formats
        for fmt in Normalizer.DATE_FORMATS:
            try:
                parsed_date = datetime.strptime(date_str, fmt).date()
                
                # Handle 2-digit year (assume 20xx for years < 50, 19xx otherwise)
                if parsed_date.year < 2000:
                    if parsed_date.year < 50:
                        parsed_date = parsed_date.replace(year=2000 + parsed_date.year)
                    else:
                        parsed_date = parsed_date.replace(year=1900 + parsed_date.year)
                
                return parsed_date
            except ValueError:
                continue
        
        return None
    
    @staticmethod
    def parse_amount(amount_str: Optional[str], default_currency: str = "INR") -> Optional[Decimal]:
        """
        Parse amount string to Decimal
        
        Handles:
        - Commas as thousands separators
        - Currency symbols (₹, Rs, $, etc.)
        - Negative amounts (with minus sign or parentheses)
        - Empty/null values
        
        Args:
            amount_str: Amount string
            default_currency: Default currency code
        
        Returns:
            Decimal or None if unparseable
        """
        if not amount_str:
            return None
        
        if isinstance(amount_str, (int, float)):
            return Decimal(str(amount_str))
        
        amount_str = str(amount_str).strip()
        if not amount_str or amount_str.lower() in ['nan', 'none', 'null', '']:
            return None
        
        # Remove currency symbols
        cleaned = re.sub(r'[₹$€£Rs]', '', amount_str, flags=re.IGNORECASE)
        
        # Remove commas (thousands separators)
        cleaned = cleaned.replace(',', '').strip()
        
        # Handle negative amounts (parentheses or minus sign)
        is_negative = False
        if cleaned.startswith('-') or cleaned.startswith('('):
            is_negative = True
            cleaned = cleaned.lstrip('-(').rstrip(')')
        
        # Remove currency codes (INR, USD, etc.)
        cleaned = re.sub(r'\b(INR|USD|EUR|GBP)\b', '', cleaned, flags=re.IGNORECASE).strip()
        
        try:
            amount = Decimal(cleaned)
            return -amount if is_negative else amount
        except (ValueError, Exception):
            return None
    
    @staticmethod
    def determine_direction(
        amount: Optional[Decimal],
        dc_str: Optional[str] = None,
        withdrawal_amt: Optional[Decimal] = None,
        deposit_amt: Optional[Decimal] = None,
    ) -> str:
        """
        Determine transaction direction (debit/credit)
        
        Priority:
        1. Explicit dc_str field
        2. Separate withdrawal/deposit columns
        3. Amount sign (negative = debit, positive = credit for most banks)
        4. Default to debit
        
        Args:
            amount: Transaction amount (may be negative)
            dc_str: Explicit direction string ("debit", "credit", "dr", "cr")
            withdrawal_amt: Withdrawal amount (for HDFC-style formats)
            deposit_amt: Deposit amount (for HDFC-style formats)
        
        Returns:
            "debit" or "credit"
        """
        # Priority 1: Explicit direction field
        if dc_str:
            dc_lower = str(dc_str).lower()
            if 'credit' in dc_lower or 'cr' in dc_lower or dc_lower == 'credit':
                return 'credit'
            if 'debit' in dc_lower or 'dr' in dc_lower or dc_lower == 'debit':
                return 'debit'
        
        # Priority 2: Separate withdrawal/deposit columns
        if withdrawal_amt and withdrawal_amt > 0 and (not deposit_amt or deposit_amt == 0):
            return 'debit'
        if deposit_amt and deposit_amt > 0 and (not withdrawal_amt or withdrawal_amt == 0):
            return 'credit'
        
        # Priority 3: Amount sign (for most Indian banks: negative = debit)
        if amount is not None:
            if amount < 0:
                return 'debit'
            # Note: Positive amounts are ambiguous - could be credit or debit
            # Default assumption: positive = credit (income/deposit)
            # This can be overridden by merchant rules or explicit direction
        
        # Default
        return 'debit'
    
    @staticmethod
    def normalize_amount(amount: Decimal, direction: str) -> Decimal:
        """
        Normalize amount to positive value with direction stored separately
        
        Args:
            amount: Amount (may be negative)
            direction: "debit" or "credit"
        
        Returns:
            Positive Decimal amount
        """
        if amount is None:
            return Decimal('0')
        
        # Ensure amount is positive
        return abs(amount)
    
    @staticmethod
    def normalize_transaction(
        parsed: Dict[str, Any],
        withdrawal_amt: Optional[Decimal] = None,
        deposit_amt: Optional[Decimal] = None,
    ) -> Dict[str, Any]:
        """
        Normalize a parsed transaction event
        
        Args:
            parsed: Parsed event dictionary with date_str, amount_str, dc, etc.
            withdrawal_amt: Optional withdrawal amount (for HDFC format)
            deposit_amt: Optional deposit amount (for HDFC format)
        
        Returns:
            Normalized dictionary with date, amount, direction, currency
        """
        # Parse date
        date_str = parsed.get("date_str") or parsed.get("date")
        txn_date = Normalizer.parse_date(date_str)
        if not txn_date:
            txn_date = date.today()  # Fallback to today
        
        # Parse amounts
        if withdrawal_amt is not None or deposit_amt is not None:
            # HDFC-style: separate withdrawal/deposit
            withdrawal = withdrawal_amt or Decimal('0')
            deposit = deposit_amt or Decimal('0')
            
            if withdrawal > 0 and deposit == 0:
                direction = 'debit'
                amount = withdrawal
            elif deposit > 0 and withdrawal == 0:
                direction = 'credit'
                amount = deposit
            else:
                # Both have values or both zero
                if withdrawal >= deposit:
                    direction = 'debit'
                    amount = withdrawal
                else:
                    direction = 'credit'
                    amount = deposit
        else:
            # Standard: single amount field
            amount_str = parsed.get("amount_str") or parsed.get("amount")
            amount = Normalizer.parse_amount(amount_str)
            if amount is None:
                amount = Decimal('0')
            
            # Determine direction
            direction = Normalizer.determine_direction(
                amount=amount,
                dc_str=parsed.get("dc"),
            )
            
            # Normalize to positive
            amount = Normalizer.normalize_amount(amount, direction)
        
        # Parse currency
        currency = parsed.get("currency") or parsed.get("currency_str") or "INR"
        if isinstance(currency, str):
            currency = currency.strip().upper()
        if not currency or len(currency) != 3:
            currency = "INR"
        
        # Parse balance (optional)
        balance_str = parsed.get("balance_str") or parsed.get("balance")
        balance = None
        if balance_str:
            balance = Normalizer.parse_amount(balance_str)
        
        return {
            "date": txn_date,
            "amount": amount,
            "direction": direction,
            "currency": currency,
            "balance": balance,
        }

