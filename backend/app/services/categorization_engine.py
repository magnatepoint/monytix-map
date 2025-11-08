"""
Categorization Engine - Rule-based transaction categorization
Implements Layer 2 of the Monytix architecture
"""
import re
from typing import Dict, Tuple, List, Optional
from decimal import Decimal
from app.database.postgresql import sync_engine
from sqlalchemy.orm import sessionmaker
SessionLocal = sessionmaker(bind=sync_engine)
from app.models.postgresql_models import Category


# Default category rules (pre-configured for all users)
DEFAULT_CATEGORIES = {
    "Food & Dining": {
        "keywords": ["restaurant", "food", "swiggy", "zomato", "uber eats", "cafe", "dining", "burger", "pizza", "foodpanda"],
        "regex_patterns": [r"swiggy|zomato|uber eats|food"],
        "priority": 1
    },
    "Shopping": {
        "keywords": ["amazon", "flipkart", "myntra", "shop", "mall", "shopping", "purchase", "buy"],
        "regex_patterns": [r"amazon|flipkart|myntra"],
        "priority": 2
    },
    "Transportation": {
        "keywords": ["uber", "ola", "taxi", "fuel", "petrol", "diesel", "metro", "bus", "railway"],
        "regex_patterns": [r"uber|ola|taxi|fuel"],
        "priority": 3
    },
    "Bills & Utilities": {
        "keywords": ["bill", "electricity", "water", "gas", "internet", "phone", "mobile", "broadband"],
        "regex_patterns": [r"bill|electricity|water"],
        "priority": 4
    },
    "Healthcare": {
        "keywords": ["hospital", "doctor", "pharmacy", "medicine", "medical", "clinic", "diagnostic"],
        "regex_patterns": [r"hospital|clinic|pharmacy"],
        "priority": 5
    },
    "Entertainment": {
        "keywords": ["movie", "cinema", "netflix", "prime", "spotify", "youtube", "bookmyshow"],
        "regex_patterns": [r"netflix|spotify|bookmyshow"],
        "priority": 6
    },
    "Education": {
        "keywords": ["school", "college", "course", "tuition", "books", "education"],
        "regex_patterns": [r"school|college|tuition"],
        "priority": 7
    },
    "Travel": {
        "keywords": ["hotel", "flight", "booking", "travel", "make my trip", "goibibo"],
        "regex_patterns": [r"hotel|flight|booking"],
        "priority": 8
    }
}


class CategorizationEngine:
    """
    Rule-based categorization engine
    Uses keyword matching and regex patterns to categorize transactions
    """
    
    def __init__(self, user_id: str = None):
        self.user_id = user_id
        self.user_rules = self._load_user_rules(user_id) if user_id else {}
        self.default_rules = DEFAULT_CATEGORIES
    
    def _load_user_rules(self, user_id: str) -> Dict:
        """Load user-specific categorization rules from database"""
        session = SessionLocal()
        try:
            categories = session.query(Category).filter(
                Category.user_id == user_id
            ).all()
            
            rules = {}
            for cat in categories:
                rules[cat.id] = {
                    "name": cat.name,
                    "keywords": cat.keywords if hasattr(cat, 'keywords') else [],
                    "regex_patterns": [],
                    "priority": 1
                }
            return rules
        finally:
            session.close()
    
    def categorize(self, description: str, merchant: Optional[str] = None, 
                   bank: Optional[str] = None) -> Tuple[str, float]:
        """
        Categorize a transaction based on description, merchant, and bank
        
        Returns:
            Tuple of (category_name, confidence_score)
        """
        description_lower = description.lower()
        merchant_lower = merchant.lower() if merchant else ""
        
        scores = {}
        
        # Check user-defined rules first
        for category_id, rules in self.user_rules.items():
            category_name = rules.get("name", "Unknown")
            score = self._calculate_score(
                description_lower, 
                merchant_lower, 
                bank, 
                rules
            )
            if score > 0:
                scores[category_name] = score
        
        # Check default rules
        for category_name, rules in self.default_rules.items():
            score = self._calculate_score(
                description_lower,
                merchant_lower,
                bank,
                rules
            )
            if category_name in scores:
                scores[category_name] += score
            elif score > 0:
                scores[category_name] = score
        
        # Return best match
        if not scores:
            return "Uncategorized", 0.0
        
        best_category = max(scores, key=scores.get)
        max_score = scores[best_category]
        
        # Normalize confidence (0-1 scale)
        confidence = min(max_score / 10.0, 1.0)
        
        return best_category, confidence
    
    def _calculate_score(self, description: str, merchant: str, bank: Optional[str], 
                        rules: Dict) -> float:
        """Calculate match score for a set of rules"""
        score = 0.0
        
        # Keyword matching
        keywords = rules.get("keywords", [])
        for keyword in keywords:
            keyword_lower = keyword.lower()
            
            # Description match
            if keyword_lower in description:
                score += 1.0
            
            # Merchant match (weighted higher)
            if merchant and keyword_lower in merchant:
                score += 2.0
        
        # Regex pattern matching
        regex_patterns = rules.get("regex_patterns", [])
        for pattern in regex_patterns:
            if re.search(pattern, description, re.IGNORECASE):
                score += 5.0
            if merchant and re.search(pattern, merchant, re.IGNORECASE):
                score += 5.0
        
        return score
    
    def detect_transaction_type(self, description: str, amount: Decimal) -> str:
        """
        Detect if transaction is debit or credit
        Based on amount sign and description keywords
        """
        description_lower = description.lower()
        
        # Negative amount suggests debit
        if amount < 0:
            return "debit"
        
        # Positive amount with credit indicators
        credit_keywords = ["credit", "deposit", "salary", "refund", "interest", "dividend"]
        if any(keyword in description_lower for keyword in credit_keywords):
            return "credit"
        
        # Debit indicators
        debit_keywords = ["debit", "payment", "purchase", "charge", "deduct"]
        if any(keyword in description_lower for keyword in debit_keywords):
            return "debit"
        
        # Default: positive = credit, negative = debit
        return "credit" if amount > 0 else "debit"


class CategorizationService:
    """
    Service layer for batch categorization and processing
    """
    
    @staticmethod
    def categorize_batch(transactions: List[Dict], user_id: str) -> List[Dict]:
        """
        Categorize a batch of transactions
        
        Args:
            transactions: List of transaction dictionaries
            user_id: User ID for user-specific rules
            
        Returns:
            List of categorized transactions with category and confidence
        """
        engine = CategorizationEngine(user_id)
        
        categorized = []
        for txn in transactions:
            description = txn.get("description", "")
            merchant = txn.get("merchant", "")
            bank = txn.get("bank", "")
            
            category, confidence = engine.categorize(description, merchant, bank)
            
            txn["category"] = category
            txn["category_confidence"] = confidence
            txn["categorized_at"] = datetime.utcnow()
            
            categorized.append(txn)
        
        return categorized
    
    @staticmethod
    def get_default_categories() -> Dict:
        """Get list of default categories"""
        return DEFAULT_CATEGORIES


# Singleton instance
def get_engine(user_id: str = None) -> CategorizationEngine:
    """Get categorization engine instance"""
    return CategorizationEngine(user_id)

