"""
Categories and Subcategories API
"""

from fastapi import APIRouter, Depends
from app.routers.auth import get_current_user, UserDep
from app.database.postgresql import SessionLocal
from app.models.spendsense_models import DimCategory, DimSubcategory
from typing import List, Dict, Any

router = APIRouter()


@router.get("/categories")
async def get_categories(user: UserDep = Depends(get_current_user)) -> List[Dict[str, Any]]:
    """Get all active categories"""
    session = SessionLocal()
    try:
        categories = session.query(DimCategory).filter(
            DimCategory.active == True
        ).order_by(DimCategory.display_order.asc(), DimCategory.category_name.asc()).all()
        
        return [
            {
                "category_code": cat.category_code,
                "category_name": cat.category_name,
                "txn_type": cat.txn_type
            }
            for cat in categories
        ]
    finally:
        session.close()


@router.get("/categories/{category_code}/subcategories")
async def get_subcategories(
    category_code: str,
    user: UserDep = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """Get all active subcategories for a category"""
    session = SessionLocal()
    try:
        subcategories = session.query(DimSubcategory).filter(
            DimSubcategory.category_code == category_code,
            DimSubcategory.active == True
        ).order_by(DimSubcategory.display_order.asc(), DimSubcategory.subcategory_name.asc()).all()
        
        return [
            {
                "subcategory_code": sub.subcategory_code,
                "subcategory_name": sub.subcategory_name,
                "category_code": sub.category_code
            }
            for sub in subcategories
        ]
    finally:
        session.close()

