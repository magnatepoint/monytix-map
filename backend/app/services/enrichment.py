"""
Enrichment Service
Rule-based enrichment with priority-based classification
"""
import re
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from decimal import Decimal
from app.database.postgresql import sync_engine
from sqlalchemy.orm import sessionmaker
from app.models.enrichment_models import (
    TransactionEnriched, TransactionOverride, EnrichmentRule, EnrichmentClassification
)
from app.models.postgresql_models import Transaction
import uuid

SessionLocal = sessionmaker(bind=sync_engine)


class EnrichmentService:
    """
    Rule-based enrichment service
    Classifies: merchant → subcategory → category → classification (income/needs/wants/assets)
    """
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.session = SessionLocal()
        self.rules = self._load_user_rules()
    
    def _load_user_rules(self) -> List[Dict]:
        """Load user-defined enrichment rules ordered by priority"""
        try:
            rules = self.session.query(EnrichmentRule).filter(
                EnrichmentRule.user_id == self.user_id,
                EnrichmentRule.is_active == True
            ).order_by(EnrichmentRule.priority.asc()).all()
            
            return [
                {
                    'id': rule.id,
                    'priority': rule.priority,
                    'name': rule.name,
                    'merchant_regex': rule.merchant_regex,
                    'description_regex': rule.description_regex,
                    'amount_min': rule.amount_min,
                    'amount_max': rule.amount_max,
                    'category': rule.category,
                    'subcategory': rule.subcategory,
                    'classification': rule.classification
                }
                for rule in rules
            ]
        except Exception as e:
            print(f"Error loading rules: {e}")
            return []
    
    def enrich_transaction(self, transaction: Dict) -> Dict[str, Any]:
        """
        Enrich a transaction with rule-based classification
        
        Args:
            transaction: Transaction dict with description, amount, merchant, etc.
            
        Returns:
            Enriched transaction dict with:
            - merchant (detected)
            - subcategory
            - category
            - classification (income/needs/wants/assets)
            - confidence score
            - rules applied
        """
        description = transaction.get('description', '').lower()
        amount = float(transaction.get('amount', 0))
        merchant = transaction.get('merchant', '').lower()
        bank = transaction.get('bank', '').lower()
        
        # Initialize enrichment result
        enrichment = {
            'merchant': transaction.get('merchant'),
            'subcategory': None,
            'category': 'Uncategorized',
            'classification': EnrichmentClassification.UNCATEGORIZED.value,
            'confidence': 0.0,
            'rules_applied': []
        }
        
        # Apply rules in priority order (lower priority = higher precedence)
        for rule in self.rules:
            if self._rule_matches(rule, description, amount, merchant, bank):
                enrichment['category'] = rule['category']
                enrichment['subcategory'] = rule.get('subcategory')
                enrichment['classification'] = rule.get('classification', EnrichmentClassification.UNCATEGORIZED.value)
                enrichment['confidence'] = 0.9  # High confidence for explicit rules
                enrichment['rules_applied'].append({
                    'rule_id': rule['id'],
                    'rule_name': rule['name'],
                    'priority': rule['priority']
                })
                break  # Stop at first match (highest priority)
        
        # If no rule matched, apply default classification
        if enrichment['category'] == 'Uncategorized':
            enrichment.update(self._apply_default_classification(transaction))
        
        return enrichment
    
    def _rule_matches(self, rule: Dict, description: str, amount: float, 
                     merchant: str, bank: str) -> bool:
        """Check if a transaction matches an enrichment rule"""
        # Check merchant regex
        if rule.get('merchant_regex'):
            try:
                if not re.search(rule['merchant_regex'], merchant, re.IGNORECASE):
                    return False
            except Exception as e:
                print(f"Error in merchant regex: {e}")
        
        # Check description regex
        if rule.get('description_regex'):
            try:
                if not re.search(rule['description_regex'], description, re.IGNORECASE):
                    return False
            except Exception as e:
                print(f"Error in description regex: {e}")
        
        # Check amount range
        if rule.get('amount_min') is not None:
            if amount < rule['amount_min']:
                return False
        
        if rule.get('amount_max') is not None:
            if amount > rule['amount_max']:
                return False
        
        return True
    
    def _apply_default_classification(self, transaction: Dict) -> Dict[str, Any]:
        """
        Apply default classification logic when no rules match
        Uses simple heuristics based on transaction characteristics
        """
        description = transaction.get('description', '').lower()
        amount = float(transaction.get('amount', 0))
        transaction_type = transaction.get('transaction_type', 'debit')
        
        # Default classification based on transaction type
        if transaction_type == 'credit' or amount > 0:
            classification = EnrichmentClassification.INCOME.value
            category = 'Income'
        else:
            # For debits, classify as needs, wants, or assets
            classification = EnrichmentClassification.NEEDS.value
            category = 'Uncategorized'
        
        return {
            'category': category,
            'classification': classification,
            'confidence': 0.5  # Lower confidence for defaults
        }
    
    def save_enrichment(self, transaction_id: str, enrichment: Dict) -> str:
        """
        Save enrichment snapshot to txn_enriched table (immutable)
        
        Returns:
            Enrichment record ID
        """
        enrichment_id = str(uuid.uuid4())
        
        enrichment_record = TransactionEnriched(
            id=enrichment_id,
            transaction_id=transaction_id,
            user_id=self.user_id,
            merchant=enrichment.get('merchant'),
            subcategory=enrichment.get('subcategory'),
            category=enrichment.get('category'),
            classification=enrichment.get('classification'),
            transaction_type_detected=enrichment.get('transaction_type'),
            enrichment_confidence=enrichment.get('confidence', 0.0),
            enrichment_rules_applied=enrichment.get('rules_applied', []),
            enrichment_timestamp=datetime.utcnow(),
            enrichment_version="1.0",
            created_at=datetime.utcnow()
        )
        
        try:
            self.session.add(enrichment_record)
            self.session.commit()
            return enrichment_id
        except Exception as e:
            self.session.rollback()
            print(f"Error saving enrichment: {e}")
            return None
    
    def create_override(self, transaction_id: str, override_data: Dict) -> str:
        """
        Create user override for enrichment
        
        Args:
            transaction_id: Transaction ID
            override_data: Dict with override fields (merchant, category, etc.)
            
        Returns:
            Override ID
        """
        override_id = str(uuid.uuid4())
        
        override = TransactionOverride(
            id=override_id,
            transaction_id=transaction_id,
            user_id=self.user_id,
            merchant_override=override_data.get('merchant'),
            subcategory_override=override_data.get('subcategory'),
            category_override=override_data.get('category'),
            classification_override=override_data.get('classification'),
            override_reason=override_data.get('reason', 'User correction'),
            override_confidence=1.0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        try:
            self.session.add(override)
            self.session.commit()
            return override_id
        except Exception as e:
            self.session.rollback()
            print(f"Error creating override: {e}")
            return None
    
    def get_effective_enrichment(self, transaction_id: str) -> Dict[str, Any]:
        """
        Get effective enrichment (takes overrides into account)
        
        Logic:
        1. Get enrichment from txn_enriched
        2. Check if override exists
        3. Merge: Override fields take precedence
        
        Returns:
            Effective enrichment dict
        """
        # Get base enrichment
        enrichment = self.session.query(TransactionEnriched).filter(
            TransactionEnriched.transaction_id == transaction_id
        ).first()
        
        # Get override if exists
        override = self.session.query(TransactionOverride).filter(
            TransactionOverride.transaction_id == transaction_id
        ).first()
        
        if not enrichment:
            return {}
        
        result = {
            'merchant': enrichment.merchant,
            'subcategory': enrichment.subcategory,
            'category': enrichment.category,
            'classification': enrichment.classification,
            'confidence': enrichment.enrichment_confidence,
            'is_overridden': override is not None
        }
        
        # Apply overrides
        if override:
            if override.merchant_override:
                result['merchant'] = override.merchant_override
            if override.subcategory_override:
                result['subcategory'] = override.subcategory_override
            if override.category_override:
                result['category'] = override.category_override
            if override.classification_override:
                result['classification'] = override.classification_override
            result['override_reason'] = override.override_reason
            result['override_at'] = override.updated_at.isoformat() if override.updated_at else None
        
        return result
    
    def enrich_transactions_batch(self, transactions: List[Dict]) -> List[Dict]:
        """
        Enrich a batch of transactions
        
        Returns:
            List of enriched transaction dicts
        """
        enriched = []
        
        for txn in transactions:
            enrichment = self.enrich_transaction(txn)
            
            # Merge with original transaction
            enriched_txn = {**txn, **enrichment}
            enriched.append(enriched_txn)
        
        return enriched
    
    def __del__(self):
        """Cleanup session"""
        if hasattr(self, 'session'):
            self.session.close()


def get_enrichment_service(user_id: str) -> EnrichmentService:
    """Get enrichment service instance"""
    return EnrichmentService(user_id)

