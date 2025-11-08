"""
Normalization Service
Validates, deduplicates, and normalizes transactions into main fact table
"""
import hashlib
import json
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from decimal import Decimal
from app.database.postgresql import sync_engine
from sqlalchemy.orm import sessionmaker
from app.models.postgresql_models import Transaction
from app.services.categorization_engine import CategorizationEngine
import uuid

SessionLocal = sessionmaker(bind=sync_engine)


class ContentHash:
    """
    Generate content hash for duplicate detection
    Based on: user_id, date, amount, currency, raw_description
    """
    
    @staticmethod
    def generate(user_id: str, transaction_date, amount: float, 
                currency: str, raw_description: str) -> str:
        """
        Generate content hash for duplicate detection
        
        Args:
            user_id: User identifier
            transaction_date: Transaction date (datetime or string)
            amount: Transaction amount
            currency: Currency code
            raw_description: Original description from source
            
        Returns:
            SHA256 hash string
        """
        # Normalize description (lowercase, strip whitespace)
        normalized_desc = raw_description.lower().strip() if raw_description else ""
        
        # Normalize date
        if isinstance(transaction_date, datetime):
            date_str = transaction_date.isoformat()
        else:
            date_str = str(transaction_date)
        
        # Create content string
        content = f"{user_id}|{date_str}|{amount}|{currency}|{normalized_desc}"
        
        # Generate hash
        return hashlib.sha256(content.encode('utf-8')).hexdigest()


class TransactionNormalizer:
    """
    Normalizes and validates transactions before loading to fact table
    """
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.categorization_engine = CategorizationEngine(user_id)
        self.session = SessionLocal()
    
    def normalize_and_validate(self, transaction: Dict) -> Dict[str, Any]:
        """
        Normalize a transaction record
        
        Args:
            transaction: Raw transaction dict
            
        Returns:
            Normalized transaction dict with validation results
        """
        normalized = {
            'raw_data': transaction,  # Keep original for reference
            'validation_errors': [],
            'is_valid': True
        }
        
        # Normalize amount
        amount_result = self._normalize_amount(transaction.get('amount', 0))
        normalized['amount'] = amount_result['value']
        if not amount_result['valid']:
            normalized['validation_errors'].append(amount_result['error'])
            normalized['is_valid'] = False
        
        # Normalize date
        date_result = self._normalize_date(transaction.get('transaction_date', ''))
        normalized['transaction_date'] = date_result['value']
        if not date_result['valid']:
            normalized['validation_errors'].append(date_result['error'])
            normalized['is_valid'] = False
        
        # Normalize description
        desc_result = self._normalize_description(transaction.get('description', ''))
        normalized['description'] = desc_result['value']
        if not desc_result['valid']:
            normalized['validation_errors'].append(desc_result['error'])
            normalized['is_valid'] = False
        
        # Other fields
        normalized['currency'] = self._normalize_currency(transaction.get('currency', 'INR'))
        normalized['merchant'] = self._normalize_merchant(transaction.get('merchant'))
        normalized['bank'] = self._normalize_string(transaction.get('bank'))
        normalized['reference_id'] = self._normalize_string(transaction.get('reference_id'))
        normalized['category'] = self._normalize_string(transaction.get('category'))
        normalized['subcategory'] = self._normalize_string(transaction.get('subcategory'))
        
        # Detect transaction type
        normalized['transaction_type'] = self._detect_transaction_type(
            transaction,
            normalized['amount'],
            normalized['description']
        )
        
        # Generate content hash
        normalized['content_hash'] = ContentHash.generate(
            self.user_id,
            normalized['transaction_date'],
            normalized['amount'],
            normalized['currency'],
            desc_result['original']
        )
        
        return normalized
    
    def deduplicate(self, transactions: List[Dict]) -> Tuple[List[Dict], List[str]]:
        """
        Remove duplicates from transaction list
        
        Returns:
            Tuple of (unique_transactions, duplicate_hashes)
        """
        seen_hashes = set()
        unique_transactions = []
        duplicate_hashes = []
        
        for txn in transactions:
            if 'content_hash' not in txn:
                # Generate hash if not present
                txn['content_hash'] = ContentHash.generate(
                    self.user_id,
                    txn.get('transaction_date', datetime.utcnow()),
                    txn.get('amount', 0),
                    txn.get('currency', 'INR'),
                    txn.get('description', '')
                )
            
            if txn['content_hash'] not in seen_hashes:
                seen_hashes.add(txn['content_hash'])
                unique_transactions.append(txn)
            else:
                duplicate_hashes.append(txn['content_hash'])
        
        return unique_transactions, duplicate_hashes
    
    def check_duplicate_exists(self, content_hash: str) -> bool:
        """
        Check if a transaction with this content hash already exists in database
        
        Returns:
            True if duplicate exists
        """
        try:
            existing = self.session.query(Transaction).filter(
                Transaction.reference_id == content_hash
            ).first()
            
            return existing is not None
        except Exception as e:
            print(f"Error checking duplicate: {e}")
            return False
    
    def load_to_fact_table(self, normalized_transaction: Dict) -> Dict[str, Any]:
        """
        Load normalized transaction to txn_fact (main fact table)
        
        Returns:
            Load result with success/error info
        """
        if not normalized_transaction.get('is_valid', False):
            return {
                'success': False,
                'error': 'Transaction failed validation',
                'errors': normalized_transaction.get('validation_errors', [])
            }
        
        # Check for duplicate
        if self.check_duplicate_exists(normalized_transaction['content_hash']):
            return {
                'success': False,
                'error': 'Duplicate transaction detected',
                'content_hash': normalized_transaction['content_hash']
            }
        
        # Apply categorization
        category, confidence = self.categorization_engine.categorize(
            normalized_transaction['description'],
            normalized_transaction.get('merchant'),
            normalized_transaction.get('bank')
        )
        
        # Create transaction record
        transaction_obj = Transaction(
            id=str(uuid.uuid4()),
            user_id=self.user_id,
            amount=Decimal(str(normalized_transaction['amount'])),
            currency=normalized_transaction['currency'],
            transaction_date=normalized_transaction['transaction_date'],
            description=normalized_transaction['description'],
            merchant=normalized_transaction.get('merchant'),
            category=normalized_transaction.get('category', category),
            subcategory=normalized_transaction.get('subcategory'),
            bank=normalized_transaction.get('bank'),
            transaction_type=normalized_transaction['transaction_type'],
            reference_id=normalized_transaction['content_hash'],  # Use hash as reference
            status='cleared',
            tags=json.dumps([]),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        try:
            self.session.add(transaction_obj)
            self.session.commit()
            
            return {
                'success': True,
                'transaction_id': transaction_obj.id,
                'category': category,
                'confidence': confidence
            }
        except Exception as e:
            self.session.rollback()
            return {
                'success': False,
                'error': str(e)
            }
    
    # Helper methods for normalization
    
    def _normalize_amount(self, amount: Any) -> Dict[str, Any]:
        """Normalize amount to float"""
        try:
            # Handle different input types
            if isinstance(amount, str):
                amount = amount.replace(',', '').replace('₹', '').replace('Rs.', '').strip()
            amount_float = float(amount)
            
            if amount_float <= 0:
                return {'value': 0.0, 'valid': False, 'error': 'Amount must be positive'}
            
            return {'value': amount_float, 'valid': True}
        except (ValueError, TypeError):
            return {'value': 0.0, 'valid': False, 'error': 'Invalid amount format'}
    
    def _normalize_date(self, date: Any) -> Dict[str, Any]:
        """Normalize date to datetime"""
        if isinstance(date, datetime):
            return {'value': date, 'valid': True, 'original': str(date)}
        
        if isinstance(date, str):
            # Try multiple date formats
            formats = [
                '%Y-%m-%d',
                '%Y-%m-%d %H:%M:%S',
                '%d-%m-%Y',
                '%d/%m/%Y',
                '%Y-%m-%dT%H:%M:%S',
                '%Y-%m-%dT%H:%M:%S.%fZ'
            ]
            
            for fmt in formats:
                try:
                    parsed = datetime.strptime(date, fmt)
                    return {'value': parsed, 'valid': True, 'original': date}
                except ValueError:
                    continue
        
        # Default to current date if invalid
        return {'value': datetime.utcnow(), 'valid': False, 'error': 'Invalid date format', 'original': str(date)}
    
    def _normalize_description(self, description: str) -> Dict[str, Any]:
        """Normalize description"""
        if not description or not isinstance(description, str):
            return {'value': '', 'valid': False, 'error': 'Description is required', 'original': str(description)}
        
        normalized = description.strip()
        
        if len(normalized) == 0:
            return {'value': normalized, 'valid': False, 'error': 'Description cannot be empty', 'original': description}
        
        if len(normalized) > 1000:
            normalized = normalized[:1000]
        
        return {'value': normalized, 'valid': True, 'original': description}
    
    def _normalize_currency(self, currency: str) -> str:
        """Normalize currency code"""
        if not currency:
            return 'INR'
        
        currency = currency.strip().upper()
        
        # Valid currencies
        valid = ['INR', 'USD', 'EUR', 'GBP', 'AUD', 'CAD']
        if currency in valid:
            return currency
        
        return 'INR'  # Default
    
    def _normalize_merchant(self, merchant: str) -> Optional[str]:
        """Normalize merchant name"""
        if not merchant:
            return None
        
        normalized = merchant.strip()
        
        if len(normalized) > 255:
            normalized = normalized[:255]
        
        return normalized if normalized else None
    
    def _normalize_string(self, value: str) -> Optional[str]:
        """Normalize any string field"""
        if not value or not isinstance(value, str):
            return None
        
        normalized = value.strip()
        return normalized if normalized else None
    
    def _detect_transaction_type(self, transaction: Dict, amount: float, description: str) -> str:
        """Detect transaction type (debit/credit)"""
        # Check explicit type first
        explicit_type = transaction.get('transaction_type', '').lower()
        if explicit_type in ['debit', 'credit']:
            return explicit_type
        
        # Detect from amount sign
        if amount < 0:
            return 'debit'
        
        # Detect from keywords
        desc_lower = description.lower()
        
        credit_keywords = ['credit', 'deposit', 'salary', 'refund', 'interest', 'dividend', 'income']
        debit_keywords = ['debit', 'payment', 'purchase', 'charge', 'deduct', 'withdrawal']
        
        if any(keyword in desc_lower for keyword in credit_keywords):
            return 'credit'
        
        if any(keyword in desc_lower for keyword in debit_keywords):
            return 'debit'
        
        # Default based on amount
        return 'debit' if amount > 0 else 'credit'
    
    def __del__(self):
        """Cleanup session"""
        if hasattr(self, 'session'):
            self.session.close()

