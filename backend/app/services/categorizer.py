"""
Categorizer Service
Applies Postgres rules to normalized events (merchant_rules, dim_category, dim_subcategory)
"""

from app.services.pg_rules_client import PGRulesClient
from app.database.postgresql import SessionLocal
from app.models.spendsense_models import DimCategory, DimSubcategory
from typing import Optional, Dict, Any
from decimal import Decimal


class Categorizer:
    """Service for categorizing transactions"""
    
    @staticmethod
    def categorize_transaction(
        merchant_name: Optional[str],
        description: Optional[str],
        user_id: Optional[str] = None,
        amount: Optional[Decimal] = None,
        direction: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Categorize a transaction using merchant rules
        
        Args:
            merchant_name: Merchant name
            description: Transaction description
            user_id: User ID (for user-specific rules)
            amount: Transaction amount (optional)
            direction: Transaction direction (optional)
        
        Returns:
            Dictionary with category_code, subcategory_code, merchant_name_norm, confidence
        """
        # Combine merchant and description for matching
        search_text = f"{merchant_name or ''} {description or ''}".strip()
        
        if not search_text:
            return {
                "category_code": None,
                "subcategory_code": None,
                "merchant_name_norm": None,
                "confidence": 0.0,
            }
        
        # Try to match merchant rules
        rule = PGRulesClient.match_merchant(
            merchant_name=merchant_name or description,
            user_id=user_id,
        )
        
        if rule:
            return {
                "category_code": rule.get("category_code"),
                "subcategory_code": rule.get("subcategory_code"),
                "merchant_name_norm": rule.get("merchant_name_norm") or merchant_name,
                "confidence": rule.get("confidence", 1.0),
            }
        
        # Fallback: no match found
        return {
            "category_code": None,
            "subcategory_code": None,
            "merchant_name_norm": merchant_name,
            "confidence": 0.0,
        }
    
    @staticmethod
    def ensure_category_exists(category_code: Optional[str]) -> bool:
        """
        Ensure category exists in dim_category (create if missing)
        
        Args:
            category_code: Category code
        
        Returns:
            True if category exists or was created, False otherwise
        """
        if not category_code:
            return False
        
        session = SessionLocal()
        try:
            # Check if category exists
            existing = session.query(DimCategory).filter(
                DimCategory.category_code == category_code
            ).first()
            
            if existing:
                return True
            
            # Map to txn_type bucket
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
            txn_type = txn_type_map.get(category_code, 'wants')
            
            # Format category name nicely
            category_name = category_code.replace('_', ' ').title()
            
            # Create category
            new_category = DimCategory(
                category_code=category_code,
                category_name=category_name,
                txn_type=txn_type,
                display_order=100,
                active=True
            )
            session.add(new_category)
            session.commit()
            
            return True
            
        except Exception as e:
            session.rollback()
            print(f"⚠️  Error ensuring category exists: {e}")
            return False
        finally:
            session.close()
    
    @staticmethod
    def ensure_subcategory_exists(subcategory_code: Optional[str], category_code: Optional[str]) -> bool:
        """
        Ensure subcategory exists in dim_subcategory (create if missing)
        
        Args:
            subcategory_code: Subcategory code
            category_code: Parent category code
        
        Returns:
            True if subcategory exists or was created, False otherwise
        """
        if not subcategory_code or not category_code:
            return False
        
        session = SessionLocal()
        try:
            # Check if subcategory exists
            existing = session.query(DimSubcategory).filter(
                DimSubcategory.subcategory_code == subcategory_code
            ).first()
            
            if existing:
                return True
            
            # Ensure parent category exists first
            Categorizer.ensure_category_exists(category_code)
            
            # Format subcategory name nicely
            subcategory_name = subcategory_code.replace('_', ' ').title()
            
            # Create subcategory
            new_subcategory = DimSubcategory(
                subcategory_code=subcategory_code,
                subcategory_name=subcategory_name,
                category_code=category_code,
                display_order=100,
                active=True
            )
            session.add(new_subcategory)
            session.commit()
            
            return True
            
        except Exception as e:
            session.rollback()
            print(f"⚠️  Error ensuring subcategory exists: {e}")
            return False
        finally:
            session.close()

