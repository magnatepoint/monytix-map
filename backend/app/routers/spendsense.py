"""
SpendSense API Endpoints
Core expense tracking and analytics
"""
from fastapi import APIRouter, Depends, Query, HTTPException, status
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from app.routers.auth import get_current_user, UserDep
from app.models.spendsense_models import TxnFact, TxnEnriched, TxnStaging
from app.database.postgresql import sync_engine, SessionLocal
from sqlalchemy import func, and_, text
from sqlalchemy.orm import sessionmaker
from decimal import Decimal
import json
import uuid

router = APIRouter()

def _infer_category(label: str) -> str:
    """Best-effort category inference for staging data without enrichment."""
    if not label:
        return "Uncategorized"
    t = label.lower()
    # Food & Dining
    if any(k in t for k in ["zomato", "swiggy", "dine", "restaurant", "truffles"]):
        return "Food"
    # Shopping / Ecommerce
    if any(k in t for k in ["amazon", "bigbazaar", "flipkart", "bazaar"]):
        return "Shopping"
    # Utilities / Bills
    if any(k in t for k in ["bescom", "bwssb", "jio", "electric", "water", "internet", "mobile"]):
        return "Utilities"
    # Transport / Travel
    if any(k in t for k in ["uber", "ola", "indigo", "flight", "metro", "train", "bus"]):
        return "Transport"
    # Housing / Rent
    if any(k in t for k in ["apartment", "rent", "society", "maintenance"]):
        return "Housing"
    # Investments / Savings
    if any(k in t for k in ["hdfc rd", "rd ", "recurring deposit", "hdfc mf", "index fund", "sip"]):
        return "Investments"
    # Banking / Fees / Interest (not counted in spending if credit elsewhere)
    if any(k in t for k in ["hdfc", "bank"]):
        return "Banking"
    return "Others"


@router.get("/stats")
async def get_spendsense_stats(
    period: str = Query("month", regex="^(day|week|month|year|all)$"),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    user: UserDep = Depends(get_current_user)
):
    """
    Get comprehensive spending statistics
    
    Period options: day, week, month, year, all
    """
    session = SessionLocal()
    
    try:
        # Calculate date range based on period
        user_uuid = uuid.UUID(user.user_id) if isinstance(user.user_id, str) else user.user_id
        
        # For "month" period, auto-detect the month with most transactions (prefer complete months)
        if period == "month" and start_date is None:
            try:
                # Find the most recent month with substantial data (at least 10 transactions)
                month_stats = session.execute(text("""
                    SELECT 
                        date_trunc('month', txn_date)::date as month,
                        COUNT(*) as txn_count
                    FROM spendsense.txn_fact
                    WHERE user_id = :uid
                    GROUP BY date_trunc('month', txn_date)
                    HAVING COUNT(*) >= 10
                    ORDER BY month DESC
                    LIMIT 1
                """), {"uid": str(user_uuid)}).fetchone()
                
                if month_stats and month_stats[0]:
                    # Use the month with most transactions
                    month_date = month_stats[0]
                    if isinstance(month_date, datetime):
                        end_date = month_date
                    else:
                        from datetime import date
                        end_date = datetime.combine(month_date if isinstance(month_date, date) else datetime.strptime(str(month_date), '%Y-%m-%d').date(), datetime.max.time())
                    
                    start_date = end_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                    # Get last day of month
                    if end_date.month == 12:
                        last_day = end_date.replace(year=end_date.year + 1, month=1, day=1) - timedelta(days=1)
                    else:
                        last_day = end_date.replace(month=end_date.month + 1, day=1) - timedelta(days=1)
                    end_date = last_day.replace(hour=23, minute=59, second=59, microsecond=999999)
                else:
                    # Fallback to most recent transaction month
                    most_recent = session.query(func.max(TxnFact.txn_date)).filter(
                        TxnFact.user_id == user_uuid
                    ).scalar()
                    if most_recent:
                        end_date = datetime.combine(most_recent, datetime.max.time())
                        start_date = end_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                        if end_date.month == 12:
                            last_day = end_date.replace(year=end_date.year + 1, month=1, day=1) - timedelta(days=1)
                        else:
                            last_day = end_date.replace(month=end_date.month + 1, day=1) - timedelta(days=1)
                        end_date = last_day.replace(hour=23, minute=59, second=59, microsecond=999999)
                    else:
                        # No transactions yet, use current month
                        end_date = datetime.utcnow()
                        start_date = end_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                        if end_date.month == 12:
                            last_day = end_date.replace(year=end_date.year + 1, month=1, day=1) - timedelta(days=1)
                        else:
                            last_day = end_date.replace(month=end_date.month + 1, day=1) - timedelta(days=1)
                        end_date = last_day.replace(hour=23, minute=59, second=59, microsecond=999999)
            except Exception as e:
                print(f"⚠️  Error detecting month: {e}")
                # Fallback to current month if query fails
                end_date = datetime.utcnow()
                start_date = end_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                if end_date.month == 12:
                    last_day = end_date.replace(year=end_date.year + 1, month=1, day=1) - timedelta(days=1)
                else:
                    last_day = end_date.replace(month=end_date.month + 1, day=1) - timedelta(days=1)
                end_date = last_day.replace(hour=23, minute=59, second=59, microsecond=999999)
        else:
            # Calculate date range based on period
            end_date = end_date or datetime.utcnow()
            if start_date is None:
                if period == "day":
                    start_date = end_date - timedelta(days=1)
                elif period == "week":
                    # Current week (Monday to Sunday)
                    days_since_monday = end_date.weekday()
                    start_date = (end_date - timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
                    end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
                elif period == "month":
                    # Current calendar month (1st to last day of month)
                    start_date = end_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                    # Get last day of month
                    if end_date.month == 12:
                        last_day = end_date.replace(year=end_date.year + 1, month=1, day=1) - timedelta(days=1)
                    else:
                        last_day = end_date.replace(month=end_date.month + 1, day=1) - timedelta(days=1)
                    end_date = last_day.replace(hour=23, minute=59, second=59, microsecond=999999)
                elif period == "year":
                    # Current calendar year (Jan 1 to Dec 31)
                    start_date = end_date.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
                    end_date = end_date.replace(month=12, day=31, hour=23, minute=59, second=59, microsecond=999999)
                else:  # all
                    start_date = datetime(2020, 1, 1)
        
        # Query transactions from spendsense.txn_fact - handle missing table gracefully
        try:
            
            # Query transactions from txn_fact with enriched categories
            transactions = session.query(
                TxnFact,
                TxnEnriched.category_code,
                TxnEnriched.subcategory_code
            ).outerjoin(
                TxnEnriched, TxnFact.txn_id == TxnEnriched.txn_id
            ).filter(
                TxnFact.user_id == user_uuid,
                TxnFact.txn_date >= start_date.date() if isinstance(start_date, datetime) else start_date,
                TxnFact.txn_date <= end_date.date() if isinstance(end_date, datetime) else end_date
            ).all()
        except Exception as e:
            # If table doesn't exist or column name mismatch, return empty results
            print(f"⚠️  Database query error (table may not exist): {str(e)}")
            transactions = []
        
        if not transactions:
            # Fallback to staging when fact table is empty
            try:
                staging = session.query(TxnStaging).filter(
                    TxnStaging.user_id == user_uuid,
                    TxnStaging.txn_date >= (start_date.date() if isinstance(start_date, datetime) else start_date),
                    TxnStaging.txn_date <= (end_date.date() if isinstance(end_date, datetime) else end_date),
                    TxnStaging.parsed_ok == True
                ).all()
                total_spending = sum(float(s.amount) for s in staging if s.direction == 'debit')
                total_income = sum(float(s.amount) for s in staging if s.direction == 'credit')
                net_flow = total_income - total_spending
                avg_txn = ((total_spending + total_income) / len(staging)) if staging else 0.0
                # No enrichment info in staging; set top_* to None
                return {
                    "period": period,
                    "total_spending": round(total_spending, 2),
                    "total_income": round(total_income, 2),
                    "net_flow": round(net_flow, 2),
                    "transaction_count": len(staging),
                    "top_category": None,
                    "top_merchant": None,
                    "avg_transaction": round(avg_txn, 2)
                }
            except Exception:
                return {
                    "period": period,
                    "total_spending": 0.0,
                    "total_income": 0.0,
                    "net_flow": 0.0,
                    "transaction_count": 0,
                    "top_category": None,
                    "top_merchant": None,
                    "avg_transaction": 0.0
                }
        
        # Calculate statistics
        # Amounts are stored as positive values, direction indicates debit/credit
        # Use Decimal for precise arithmetic to avoid floating point errors
        from decimal import Decimal
        # Exclude investments and loans from spending (they're assets/liabilities, not expenses)
        # Also exclude transfers from both spending and income
        exclude_from_spending = {'investments', 'loans', 'transfers', 'credit_cards'}
        exclude_from_income = {'transfers'}
        
        total_spending = sum(
            Decimal(str(txn.amount)) 
            for txn, cat, subcat in transactions 
            if txn.direction == 'debit' 
            and (cat is None or cat not in exclude_from_spending)
        )
        total_income = sum(
            Decimal(str(txn.amount)) 
            for txn, cat, subcat in transactions 
            if txn.direction == 'credit' 
            and (cat is None or cat not in exclude_from_income)
        )
        # Net flow = income - spending (excludes investments, loans, transfers, credit cards)
        # This gives a clearer picture of actual cash flow
        net_flow = float(total_income - total_spending)
        
        # Top category and merchant
        category_totals = {}
        merchant_totals = {}
        
        for txn, cat, subcat in transactions:
            if cat:
                category_totals[cat] = category_totals.get(cat, 0) + float(txn.amount)
            if txn.merchant_name_norm:
                merchant_totals[txn.merchant_name_norm] = merchant_totals.get(txn.merchant_name_norm, 0) + float(txn.amount)
        
        top_category = max(category_totals, key=category_totals.get) if category_totals else None
        top_merchant = max(merchant_totals, key=merchant_totals.get) if merchant_totals else None
        
        avg_transaction = float((total_spending + total_income) / len(transactions)) if transactions else 0.0
        
        # Calculate cumulative balance (all-time net flow, excluding investments/loans)
        try:
            all_transactions = session.query(
                TxnFact,
                TxnEnriched.category_code
            ).outerjoin(
                TxnEnriched, TxnFact.txn_id == TxnEnriched.txn_id
            ).filter(
                TxnFact.user_id == user_uuid
            ).all()
            
            # Exclude investments, loans, transfers, credit_cards from cumulative balance
            exclude_from_spending = {'investments', 'loans', 'transfers', 'credit_cards'}
            exclude_from_income = {'transfers'}
            
            # Use Decimal for precise arithmetic
            cumulative_income = sum(
                Decimal(str(txn.amount)) 
                for txn, cat in all_transactions 
                if txn.direction == 'credit' 
                and (cat is None or cat not in exclude_from_income)
            )
            cumulative_spending = sum(
                Decimal(str(txn.amount)) 
                for txn, cat in all_transactions 
                if txn.direction == 'debit' 
                and (cat is None or cat not in exclude_from_spending)
            )
            cumulative_balance = float(cumulative_income - cumulative_spending)
        except Exception as e:
            print(f"⚠️  Error calculating cumulative balance: {e}")
            # Fallback to monthly net flow if calculation fails
            cumulative_balance = net_flow
        
        return {
            "period": period,
            "total_spending": float(total_spending),
            "total_income": float(total_income),
            "net_flow": net_flow,
            "cumulative_balance": cumulative_balance,
            "transaction_count": len(transactions),
            "top_category": top_category,
            "top_merchant": top_merchant,
            "avg_transaction": round(avg_transaction, 2),
            "period_start": start_date.isoformat() if isinstance(start_date, datetime) else str(start_date),
            "period_end": end_date.isoformat() if isinstance(end_date, datetime) else str(end_date)
        }
    finally:
        session.close()


@router.get("/by-category")
async def get_spending_by_category(
    period: str = Query("month", regex="^(day|week|month|year|all)$"),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    user: UserDep = Depends(get_current_user)
):
    """
    Get spending breakdown by category
    """
    session = SessionLocal()
    
    try:
        # Calculate date range
        user_uuid = uuid.UUID(user.user_id) if isinstance(user.user_id, str) else user.user_id
        
        # For "month" period, auto-detect the most recent month with substantial data
        if period == "month" and start_date is None:
            try:
                # Find the most recent month with substantial data (at least 10 transactions)
                month_stats = session.execute(text("""
                    SELECT 
                        date_trunc('month', txn_date)::date as month,
                        COUNT(*) as txn_count
                    FROM spendsense.txn_fact
                    WHERE user_id = :uid
                    GROUP BY date_trunc('month', txn_date)
                    HAVING COUNT(*) >= 10
                    ORDER BY month DESC
                    LIMIT 1
                """), {"uid": str(user_uuid)}).fetchone()
                
                if month_stats and month_stats[0]:
                    # Use the month with most transactions
                    month_date = month_stats[0]
                    if isinstance(month_date, datetime):
                        end_date = month_date
                    else:
                        from datetime import date
                        end_date = datetime.combine(month_date if isinstance(month_date, date) else datetime.strptime(str(month_date), '%Y-%m-%d').date(), datetime.max.time())
                    
                    start_date = end_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                    if end_date.month == 12:
                        last_day = end_date.replace(year=end_date.year + 1, month=1, day=1) - timedelta(days=1)
                    else:
                        last_day = end_date.replace(month=end_date.month + 1, day=1) - timedelta(days=1)
                    end_date = last_day.replace(hour=23, minute=59, second=59, microsecond=999999)
                else:
                    # Fallback to most recent transaction month
                    most_recent = session.query(func.max(TxnFact.txn_date)).filter(
                        TxnFact.user_id == user_uuid
                    ).scalar()
                    if most_recent:
                        end_date = datetime.combine(most_recent, datetime.max.time())
                        start_date = end_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                        if end_date.month == 12:
                            last_day = end_date.replace(year=end_date.year + 1, month=1, day=1) - timedelta(days=1)
                        else:
                            last_day = end_date.replace(month=end_date.month + 1, day=1) - timedelta(days=1)
                        end_date = last_day.replace(hour=23, minute=59, second=59, microsecond=999999)
                    else:
                        end_date = datetime.utcnow()
                        start_date = end_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                        if end_date.month == 12:
                            last_day = end_date.replace(year=end_date.year + 1, month=1, day=1) - timedelta(days=1)
                        else:
                            last_day = end_date.replace(month=end_date.month + 1, day=1) - timedelta(days=1)
                        end_date = last_day.replace(hour=23, minute=59, second=59, microsecond=999999)
            except Exception as e:
                print(f"⚠️  Error detecting month for by-category: {e}")
                end_date = datetime.utcnow()
                start_date = end_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                if end_date.month == 12:
                    last_day = end_date.replace(year=end_date.year + 1, month=1, day=1) - timedelta(days=1)
                else:
                    last_day = end_date.replace(month=end_date.month + 1, day=1) - timedelta(days=1)
                end_date = last_day.replace(hour=23, minute=59, second=59, microsecond=999999)
        else:
            end_date = end_date or datetime.utcnow()
            if start_date is None:
                if period == "day":
                    start_date = end_date - timedelta(days=1)
                elif period == "week":
                    days_since_monday = end_date.weekday()
                    start_date = (end_date - timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
                    end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
                elif period == "month":
                    start_date = end_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                    if end_date.month == 12:
                        last_day = end_date.replace(year=end_date.year + 1, month=1, day=1) - timedelta(days=1)
                    else:
                        last_day = end_date.replace(month=end_date.month + 1, day=1) - timedelta(days=1)
                    end_date = last_day.replace(hour=23, minute=59, second=59, microsecond=999999)
                elif period == "year":
                    start_date = end_date.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
                    end_date = end_date.replace(month=12, day=31, hour=23, minute=59, second=59, microsecond=999999)
                else:  # all
                    start_date = datetime(2020, 1, 1)
        
        # Query from TxnFact with TxnEnriched for categories
        # Group by category code from TxnEnriched
        try:
            result = session.query(
                TxnEnriched.category_code,
                func.sum(func.abs(TxnFact.amount)).label('total'),
                func.count(TxnFact.txn_id).label('count')
            ).outerjoin(
                TxnEnriched, TxnFact.txn_id == TxnEnriched.txn_id
            ).filter(
                TxnFact.user_id == user_uuid,
                TxnFact.txn_date >= start_date.date() if isinstance(start_date, datetime) else start_date,
                TxnFact.txn_date <= end_date.date() if isinstance(end_date, datetime) else end_date,
                TxnFact.direction == "debit",  # Only debits (spending)
                # Exclude income and transfers categories
                (TxnEnriched.category_code.is_(None)) | (
                    (TxnEnriched.category_code != 'transfers') &
                    (TxnEnriched.category_code != 'income')
                )
            ).group_by(
                TxnEnriched.category_code
            ).order_by(
                func.sum(func.abs(TxnFact.amount)).desc()
            ).all()
        except Exception as e:
            # If tables don't exist or query fails, return empty result
            print(f"⚠️  Database query error in by-category: {str(e)}")
            return {
                "period": period,
                "categories": [],
                "total": 0.0,
                "currency": "INR"
            }
        
        # Fallback to staging when no categories or no fact data
        if not result:
            try:
                staging_rows = session.query(TxnStaging).filter(
                    TxnStaging.user_id == user_uuid,
                    TxnStaging.txn_date >= start_date.date() if isinstance(start_date, datetime) else start_date,
                    TxnStaging.txn_date <= end_date.date() if isinstance(end_date, datetime) else end_date,
                    TxnStaging.direction == 'debit',
                    TxnStaging.parsed_ok == True
                ).all()

                totals = {}
                counts = {}
                for s in staging_rows:
                    cat = _infer_category(s.merchant_raw or s.description_raw or "")
                    amt = float(s.amount)
                    totals[cat] = totals.get(cat, 0.0) + amt
                    counts[cat] = counts.get(cat, 0) + 1

                total_amount = sum(totals.values())
                breakdown = []
                for cat, amt in sorted(totals.items(), key=lambda x: x[1], reverse=True):
                    percentage = (amt / total_amount * 100) if total_amount > 0 else 0
                    breakdown.append({
                        "category": cat,
                        "amount": round(amt, 2),
                        "percentage": round(percentage, 2),
                        "transaction_count": counts.get(cat, 0)
                    })

                return {
                    "period": period,
                    "categories": breakdown,
                    "total": round(total_amount, 2),
                    "currency": "INR"
                }
            except Exception as e:
                print(f"⚠️  By-category staging fallback failed: {str(e)}")
                return {
                    "period": period,
                    "categories": [],
                    "total": 0.0,
                    "currency": "INR"
                }
        
        total_amount = sum(float(row.total) for row in result)
        
        breakdown = []
        for row in result:
            percentage = (float(row.total) / total_amount * 100) if total_amount > 0 else 0
            breakdown.append({
                "category": row.category_code or "Uncategorized",
                "amount": float(row.total),
                "percentage": round(percentage, 2),
                "transaction_count": row.count
            })
        
        return {
            "period": period,
            "categories": breakdown,
            "total": float(total_amount),
            "currency": "INR"
        }
    finally:
        session.close()


@router.get("/trends")
async def get_spending_trends(
    period: str = Query("3months", regex="^(1month|3months|6months|1year)$"),
    user: UserDep = Depends(get_current_user)
):
    """
    Get spending trends over time
    
    Returns: Monthly/weekly spending data
    """
    session = SessionLocal()
    
    try:
        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days={
            "1month": 30,
            "3months": 90,
            "6months": 180,
            "1year": 365
        }.get(period, 90))
        
        user_uuid = uuid.UUID(user.user_id) if isinstance(user.user_id, str) else user.user_id
        
        # Group by month from TxnFact
        try:
            result = session.query(
                func.date_trunc('month', TxnFact.txn_date).label('month'),
                func.sum(func.abs(TxnFact.amount)).label('spending')
            ).filter(
                TxnFact.user_id == user_uuid,
                TxnFact.txn_date >= start_date.date() if isinstance(start_date, datetime) else start_date,
                TxnFact.txn_date <= end_date.date() if isinstance(end_date, datetime) else end_date,
                TxnFact.direction == "debit"
            ).group_by(func.date_trunc('month', TxnFact.txn_date)).order_by('month').all()
        except Exception as e:
            print(f"⚠️  Database query error in trends: {str(e)}")
            return {
                "period": period,
                "trends": []
            }
        
        # Fallback to staging when no fact data
        if not result:
            try:
                staging_trend = session.query(
                    func.date_trunc('month', TxnStaging.txn_date).label('month'),
                    func.sum(func.abs(TxnStaging.amount)).label('spending')
                ).filter(
                    TxnStaging.user_id == user_uuid,
                    TxnStaging.txn_date >= start_date.date() if isinstance(start_date, datetime) else start_date,
                    TxnStaging.txn_date <= end_date.date() if isinstance(end_date, datetime) else end_date,
                    TxnStaging.direction == 'debit',
                    TxnStaging.parsed_ok == True
                ).group_by(func.date_trunc('month', TxnStaging.txn_date)).order_by('month').all()

                trends = []
                for row in staging_trend:
                    trends.append({
                        "period": row.month.strftime("%Y-%m"),
                        "spending": float(row.spending),
                        "date": row.month.isoformat()
                    })
                return {"period": period, "trends": trends}
            except Exception as e:
                print(f"⚠️  Trends staging fallback failed: {str(e)}")
                return {"period": period, "trends": []}
        
        trends = []
        for row in result:
            trends.append({
                "period": row.month.strftime("%Y-%m"),
                "spending": float(row.spending),
                "date": row.month.isoformat()
            })
        
        return {
            "period": period,
            "trends": trends
        }
    finally:
        session.close()


@router.get("/kpis")
async def get_kpis(
    period: str = Query("month", regex="^(month|year)$"),
    user: UserDep = Depends(get_current_user)
):
    """Return KPI summary for dashboard. Uses materialized views if they exist,
    otherwise falls back to computing from txn_fact.
    """
    session = SessionLocal()
    try:
        user_uuid = uuid.UUID(user.user_id) if isinstance(user.user_id, str) else user.user_id
        
        # Determine date range based on period
        end_date = datetime.utcnow().date()
        if period == "month":
            start_date = (datetime.utcnow() - timedelta(days=30)).date()
        else:  # year
            start_date = (datetime.utcnow() - timedelta(days=365)).date()
        
        # Try MV first - compute totals from the view
        try:
            view = "spendsense.mv_spendsense_dashboard_user_month"
            row = session.execute(text(
                """
                SELECT 
                    income_amt,
                    needs_amt,
                    wants_amt,
                    assets_amt,
                    month
                FROM """ + view + """
                WHERE user_id = :uid
                ORDER BY month DESC
                LIMIT 1
                """
            ), {"uid": str(user_uuid)}).fetchone()
            
            if row:
                income_amt, needs_amt, wants_amt, assets_amt, month = row
                # Exclude investments (assets_amt) and loans from spending for net flow calculation
                # Investments and loans are tracked separately (assets/liabilities)
                total_spending = float(needs_amt or 0) + float(wants_amt or 0)  # Exclude assets_amt (investments)
                total_income = float(income_amt or 0)
                # Net flow = income - operational spending (excludes investments, loans, transfers)
                net_flow = total_income - total_spending
                
                # Get transaction count from fact table for the month
                month_start = month.replace(day=1) if isinstance(month, datetime) else month
                from calendar import monthrange
                month_end = month_start.replace(day=monthrange(month_start.year, month_start.month)[1]) if isinstance(month_start, datetime) else month_start
                
                txn_count = session.execute(text("""
                    SELECT COUNT(*) 
                    FROM spendsense.txn_fact
                    WHERE user_id = :uid
                    AND txn_date >= :start
                    AND txn_date <= :end
                """), {"uid": str(user_uuid), "start": month_start, "end": month_end}).scalar() or 0
                
                return {
                    "period": period,
                    "total_spending": total_spending,
                    "total_income": total_income,
                    "net_flow": net_flow,
                    "transaction_count": txn_count
                }
        except Exception as e:
            print(f"⚠️  Materialized view query failed: {e}")

        # Fallback compute from fact table for date range
        try:
            txns = session.query(
                TxnFact,
                TxnEnriched.category_code
            ).outerjoin(
                TxnEnriched, TxnFact.txn_id == TxnEnriched.txn_id
            ).filter(
                TxnFact.user_id == user_uuid,
                TxnFact.txn_date >= start_date,
                TxnFact.txn_date <= end_date
            ).all()
            
            # Exclude investments, loans, transfers, credit_cards from spending
            exclude_from_spending = {'investments', 'loans', 'transfers', 'credit_cards'}
            exclude_from_income = {'transfers'}
            
            total_spending = sum(
                float(txn.amount) 
                for txn, cat in txns 
                if txn.direction == 'debit' 
                and (cat is None or cat not in exclude_from_spending)
            )
            total_income = sum(
                float(txn.amount) 
                for txn, cat in txns 
                if txn.direction == 'credit' 
                and (cat is None or cat not in exclude_from_income)
            )
            net_flow = total_income - total_spending
            return {
                "period": period,
                "total_spending": total_spending,
                "total_income": total_income,
                "net_flow": net_flow,
                "transaction_count": len(txns)
            }
        except Exception as e:
            print(f"⚠️  Fact table query failed: {e}")
            return {
                "period": period,
                "total_spending": 0.0,
                "total_income": 0.0,
                "net_flow": 0.0,
                "transaction_count": 0
            }
    finally:
        session.close()


def _rebuild_kpis_for_user(session, user_id_str: str):
    """Helper function to rebuild KPIs for a user (can be called from ETL pipeline).
    
    Populates:
      - spendsense.kpi_type_split_monthly
      - spendsense.kpi_category_monthly
      - spendsense.kpi_recurring_merchants_monthly
      - spendsense.kpi_spending_leaks_monthly
      - (optional) spendsense.kpi_type_split_daily if table exists
    """
    import uuid as _uuid
    user_uuid = _uuid.UUID(user_id_str) if isinstance(user_id_str, str) else user_id_str

    # If no facts, exit early
    minmax = session.execute(text(
        "SELECT min(txn_date), max(txn_date) FROM spendsense.txn_fact WHERE user_id = :uid"
    ), {"uid": str(user_uuid)}).fetchone()
    if not minmax or not minmax[0]:
        return

    # ---------- Type Split Monthly ----------
    session.execute(text(
        "DELETE FROM spendsense.kpi_type_split_monthly WHERE user_id = :uid"
    ), {"uid": str(user_uuid)})

    session.execute(text(
        """
        INSERT INTO spendsense.kpi_type_split_monthly
            (user_id, month, income_amt, needs_amt, wants_amt, assets_amt, created_at)
        SELECT
            tf.user_id,
            date_trunc('month', tf.txn_date)::date AS month,
            SUM(CASE WHEN tf.direction = 'credit' THEN tf.amount ELSE 0 END) AS income_amt,
            SUM(CASE WHEN tf.direction = 'debit' AND COALESCE(dc.txn_type,'wants') = 'needs' THEN tf.amount ELSE 0 END) AS needs_amt,
            SUM(CASE WHEN tf.direction = 'debit' AND COALESCE(dc.txn_type,'wants') = 'wants' THEN tf.amount ELSE 0 END) AS wants_amt,
            SUM(CASE WHEN tf.direction = 'debit' AND COALESCE(dc.txn_type,'wants') = 'assets' THEN tf.amount ELSE 0 END) AS assets_amt,
            NOW()
        FROM spendsense.txn_fact tf
        LEFT JOIN spendsense.txn_enriched te ON te.txn_id = tf.txn_id
        LEFT JOIN spendsense.dim_category dc ON dc.category_code = te.category_code
        WHERE tf.user_id = :uid
          AND COALESCE(te.category_code,'') <> 'transfers'
        GROUP BY tf.user_id, date_trunc('month', tf.txn_date)
        """
    ), {"uid": str(user_uuid)})

    # ---------- Category Monthly ----------
    session.execute(text(
        "DELETE FROM spendsense.kpi_category_monthly WHERE user_id = :uid"
    ), {"uid": str(user_uuid)})

    session.execute(text(
        """
        INSERT INTO spendsense.kpi_category_monthly
            (user_id, month, category_code, spend_amt)
        SELECT
            tf.user_id,
            date_trunc('month', tf.txn_date)::date AS month,
            COALESCE(te.category_code, 'others') AS category_code,
            SUM(CASE WHEN tf.direction='debit' THEN tf.amount ELSE 0 END) AS spend_amt
        FROM spendsense.txn_fact tf
        LEFT JOIN spendsense.txn_enriched te ON te.txn_id = tf.txn_id
        WHERE tf.user_id = :uid
          AND COALESCE(te.category_code,'') <> 'transfers'
          AND COALESCE(te.category_code,'') <> 'income'  -- Exclude income from spending
        GROUP BY tf.user_id, date_trunc('month', tf.txn_date), COALESCE(te.category_code, 'others')
        """
    ), {"uid": str(user_uuid)})

    # ---------- Recurring Merchants Monthly ----------
    session.execute(text(
        "DELETE FROM spendsense.kpi_recurring_merchants_monthly WHERE user_id = :uid"
    ), {"uid": str(user_uuid)})

    session.execute(text(
        """
        INSERT INTO spendsense.kpi_recurring_merchants_monthly
            (user_id, month, merchant_name_norm, txn_count, total_amt)
        SELECT
            tf.user_id,
            date_trunc('month', tf.txn_date)::date AS month,
            tf.merchant_name_norm,
            COUNT(*) AS txn_count,
            SUM(CASE WHEN tf.direction='debit' THEN tf.amount ELSE 0 END) AS total_amt
        FROM spendsense.txn_fact tf
        WHERE tf.user_id = :uid AND tf.merchant_name_norm IS NOT NULL
        GROUP BY tf.user_id, date_trunc('month', tf.txn_date), tf.merchant_name_norm
        HAVING COUNT(*) >= 3
        """
    ), {"uid": str(user_uuid)})

    # ---------- Spending Leaks Monthly ----------
    session.execute(text(
        "DELETE FROM spendsense.kpi_spending_leaks_monthly WHERE user_id = :uid"
    ), {"uid": str(user_uuid)})

    session.execute(text(
        """
        WITH wants AS (
            SELECT
                COALESCE(te.category_code,'others') AS category_code,
                date_trunc('month', tf.txn_date)::date AS month,
                SUM(CASE WHEN tf.direction='debit' THEN tf.amount ELSE 0 END) AS spend_amt
            FROM spendsense.txn_fact tf
            LEFT JOIN spendsense.txn_enriched te ON te.txn_id = tf.txn_id
            LEFT JOIN spendsense.dim_category dc ON dc.category_code = te.category_code
            WHERE tf.user_id = :uid 
              AND COALESCE(te.category_code,'') <> 'transfers'
              AND COALESCE(dc.txn_type,'wants')='wants'
            GROUP BY date_trunc('month', tf.txn_date), COALESCE(te.category_code,'others')
        ), rnk AS (
            SELECT w.*, ROW_NUMBER() OVER (PARTITION BY w.month ORDER BY w.spend_amt DESC) AS rn
            FROM wants w
        )
        INSERT INTO spendsense.kpi_spending_leaks_monthly
            (user_id, month, rank, category_code, leak_amt)
        SELECT CAST(:uid AS uuid) AS user_id, r.month, r.rn AS rank, r.category_code, r.spend_amt AS leak_amt
        FROM rnk r WHERE r.rn <= 3
        """
    ), {"uid": str(user_uuid)})

    # ---------- Type Split Daily (optional) ----------
    try:
        session.execute(text(
            "DELETE FROM spendsense.kpi_type_split_daily WHERE user_id = :uid"
        ), {"uid": str(user_uuid)})

        session.execute(text(
            """
            INSERT INTO spendsense.kpi_type_split_daily
                (user_id, dt, income_amt, needs_amt, wants_amt, assets_amt, created_at)
            SELECT
                tf.user_id,
                date_trunc('day', tf.txn_date)::date AS dt,
                SUM(CASE WHEN tf.direction = 'credit' THEN tf.amount ELSE 0 END) AS income_amt,
                SUM(CASE WHEN tf.direction = 'debit' AND COALESCE(dc.txn_type,'wants') = 'needs' THEN tf.amount ELSE 0 END) AS needs_amt,
                SUM(CASE WHEN tf.direction = 'debit' AND COALESCE(dc.txn_type,'wants') = 'wants' THEN tf.amount ELSE 0 END) AS wants_amt,
                SUM(CASE WHEN tf.direction = 'debit' AND COALESCE(dc.txn_type,'wants') = 'assets' THEN tf.amount ELSE 0 END) AS assets_amt,
                NOW()
            FROM spendsense.txn_fact tf
            LEFT JOIN spendsense.txn_enriched te ON te.txn_id = tf.txn_id
            LEFT JOIN spendsense.dim_category dc ON dc.category_code = te.category_code
            WHERE tf.user_id = :uid
              AND COALESCE(te.category_code,'') <> 'transfers'
            GROUP BY tf.user_id, date_trunc('day', tf.txn_date)
            """
        ), {"uid": str(user_uuid)})
    except Exception:
        pass


@router.post("/kpis/rebuild")
async def rebuild_kpis(
    user: UserDep = Depends(get_current_user),
    threshold_small_txn: float = 1000.0
):
    """Rebuild 5 KPIs from txn_fact for the current user.

    Populates:
      - spendsense.kpi_type_split_monthly
      - spendsense.kpi_category_monthly
      - spendsense.kpi_recurring_merchants_monthly
      - spendsense.kpi_spending_leaks_monthly
      - (optional) spendsense.kpi_type_split_daily if table exists
    """
    session = SessionLocal()
    try:
        user_uuid = uuid.UUID(user.user_id) if isinstance(user.user_id, str) else user.user_id

        # If no facts, exit early
        minmax = session.execute(text(
            "SELECT min(txn_date), max(txn_date) FROM spendsense.txn_fact WHERE user_id = :uid"
        ), {"uid": str(user_uuid)}).fetchone()
        if not minmax or not minmax[0]:
            return {"message": "No transactions in txn_fact"}
        
        # Call the helper function
        _rebuild_kpis_for_user(session, user.user_id)
        
        session.commit()
        return {"message": "KPIs rebuilt"}
    finally:
        session.close()


@router.get("/merchants")
async def get_top_merchants(
    limit: int = Query(10, ge=1, le=50),
    period: str = Query("month", regex="^(day|week|month|year)$"),
    user: UserDep = Depends(get_current_user)
):
    """
    Get top merchants by spending
    """
    session = SessionLocal()
    
    try:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days={
            "day": 1,
            "week": 7,
            "month": 30,
            "year": 365
        }.get(period, 30))
        
        user_uuid = uuid.UUID(user.user_id) if isinstance(user.user_id, str) else user.user_id
        
        # Query from TxnFact using merchant_name_norm
        try:
            result = session.query(
                TxnFact.merchant_name_norm,
                func.sum(func.abs(TxnFact.amount)).label('total'),
                func.count(TxnFact.txn_id).label('count')
            ).filter(
                TxnFact.user_id == user_uuid,
                TxnFact.txn_date >= start_date.date() if isinstance(start_date, datetime) else start_date,
                TxnFact.txn_date <= end_date.date() if isinstance(end_date, datetime) else end_date,
                TxnFact.direction == "debit",
                TxnFact.merchant_name_norm.isnot(None)
            ).group_by(TxnFact.merchant_name_norm).order_by(func.sum(func.abs(TxnFact.amount)).desc()).limit(limit).all()
        except Exception as e:
            print(f"⚠️  Database query error in merchants: {str(e)}")
            return {
                "period": period,
                "merchants": []
            }
        
        merchants = []
        for row in result:
            merchants.append({
                "merchant": row.merchant_name_norm or "Unknown",
                "total_spending": float(row.total),
                "transaction_count": row.count
            })
        
        return {
            "period": period,
            "merchants": merchants
        }
    finally:
        session.close()


@router.get("/insights")
async def get_insights(
    user: UserDep = Depends(get_current_user)
):
    """Return spending insights.

    Shows top 5 categories by spending amount for the most recent month with substantial data.
    Returns [{ type, category, message }].
    """
    session = SessionLocal()
    try:
        user_uuid = uuid.UUID(user.user_id) if isinstance(user.user_id, str) else user.user_id
        
        # Find the most recent month with substantial data (at least 10 transactions)
        month_stats = session.execute(text("""
            SELECT 
                date_trunc('month', txn_date)::date as month,
                COUNT(*) as txn_count
            FROM spendsense.txn_fact
            WHERE user_id = :uid
            GROUP BY date_trunc('month', txn_date)
            HAVING COUNT(*) >= 10
            ORDER BY month DESC
            LIMIT 1
        """), {"uid": str(user_uuid)}).fetchone()
        
        if not month_stats or not month_stats[0]:
            return {"insights": []}
        
        target_month = month_stats[0]
        
        # Get top 5 categories by spending for that month from KPI table
        try:
            category_rows = session.execute(text("""
                SELECT 
                    k.category_code,
                    dc.category_name,
                    k.spend_amt
                FROM spendsense.kpi_category_monthly k
                LEFT JOIN spendsense.dim_category dc ON dc.category_code = k.category_code
                WHERE k.user_id = :uid
                AND k.month = :target_month
                AND k.category_code NOT IN ('income', 'transfers')
                AND k.spend_amt > 0
                ORDER BY k.spend_amt DESC
                LIMIT 5
            """), {"uid": str(user_uuid), "target_month": target_month}).fetchall()
            
            insights = []
            for cat_code, cat_name, amt in category_rows:
                # Format category name nicely
                display_name = cat_name or cat_code or 'Uncategorized'
                insights.append({
                    "type": "top_category",
                    "category": cat_code or 'Uncategorized',
                    "message": f"{display_name}: ₹{round(float(amt)):.0f}"
                })
            
            if insights:
                return {"insights": insights}
        except Exception as e:
            print(f"⚠️  Error fetching top categories from KPI: {e}")
        
        # Fallback: compute from fact table for the target month
        try:
            from datetime import date
            month_date = target_month if isinstance(target_month, date) else datetime.strptime(str(target_month), '%Y-%m-%d').date()
            month_start = datetime.combine(month_date.replace(day=1), datetime.min.time())
            if month_date.month == 12:
                month_end = datetime.combine(date(month_date.year + 1, 1, 1) - timedelta(days=1), datetime.max.time())
            else:
                month_end = datetime.combine(date(month_date.year, month_date.month + 1, 1) - timedelta(days=1), datetime.max.time())
            
            rows = session.query(
                TxnEnriched.category_code,
                func.sum(func.abs(TxnFact.amount)).label('spend')
            ).join(TxnEnriched, TxnFact.txn_id == TxnEnriched.txn_id).filter(
                TxnFact.user_id == user_uuid,
                TxnFact.txn_date >= month_start.date(),
                TxnFact.txn_date <= month_end.date(),
                TxnFact.direction == 'debit',  # Only debits (spending)
                TxnEnriched.category_code.notin_(['income', 'transfers'])  # Exclude income and transfers
            ).group_by(TxnEnriched.category_code).order_by(func.sum(func.abs(TxnFact.amount)).desc()).limit(5).all()

            insights = []
            for cat, amt in rows:
                cat_name = session.execute(text("""
                    SELECT category_name FROM spendsense.dim_category WHERE category_code = :cat
                """), {"cat": cat or 'others'}).scalar() or cat or 'Uncategorized'
                
                insights.append({
                    "type": "top_category",
                    "category": cat or 'Uncategorized',
                    "message": f"{cat_name}: ₹{round(float(amt or 0)):.0f}"
                })
            return {"insights": insights}
        except Exception as e:
            print(f"⚠️  Error in fallback calculation: {e}")
            return {"insights": []}
    finally:
        session.close()


@router.get("/top-categories")
async def get_top_categories(
    limit: int = Query(3, ge=1, le=10),
    period: str = Query("month", regex="^(day|week|month|year)$"),
    user: UserDep = Depends(get_current_user)
):
    """
    Get top N spending categories
    Core Objective: Visual Simplicity - Top 3 spending categories
    """
    session = SessionLocal()
    
    try:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days={
            "day": 1,
            "week": 7,
            "month": 30,
            "year": 365
        }.get(period, 30))
        
        user_uuid = uuid.UUID(user.user_id) if isinstance(user.user_id, str) else user.user_id
        
        try:
            result = session.query(
                TxnEnriched.category_code,
                func.sum(func.abs(TxnFact.amount)).label('total'),
                func.count(TxnFact.txn_id).label('count')
            ).join(
                TxnEnriched, TxnFact.txn_id == TxnEnriched.txn_id
            ).filter(
                TxnFact.user_id == user_uuid,
                TxnFact.txn_date >= start_date.date() if isinstance(start_date, datetime) else start_date,
                TxnFact.txn_date <= end_date.date() if isinstance(end_date, datetime) else end_date,
                TxnFact.direction == "debit",  # Only debits (spending)
                TxnEnriched.category_code.isnot(None),
                # Exclude income and transfers
                TxnEnriched.category_code != 'income',
                TxnEnriched.category_code != 'transfers'
            ).group_by(TxnEnriched.category_code).order_by(func.sum(func.abs(TxnFact.amount)).desc()).limit(limit).all()
            
            categories = []
            for row in result:
                categories.append({
                    "category": row.category_code,
                    "total_spending": float(row.total),
                    "transaction_count": row.count
                })
        except Exception as e:
            print(f"⚠️  Database query error in top-categories: {str(e)}")
            categories = []
        
        return {
            "period": period,
            "categories": categories
        }
    finally:
        session.close()


@router.get("/leaks")
async def detect_spending_leaks(
    threshold: float = Query(1000.0, ge=100.0),
    period: str = Query("month", regex="^(week|month|year)$"),
    user: UserDep = Depends(get_current_user)
):
    """
    Detect spending leaks (small recurring transactions that add up)
    Core Objective: Behavioral Clarity - Help users understand spending
    """
    session = SessionLocal()
    
    try:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days={
            "week": 7,
            "month": 30,
            "year": 365
        }.get(period, 30))
        
        user_uuid = uuid.UUID(user.user_id) if isinstance(user.user_id, str) else user.user_id
        
        # Find merchants with many small transactions
        try:
            result = session.query(
                TxnFact.merchant_name_norm,
                func.count(TxnFact.txn_id).label('count'),
                func.sum(func.abs(TxnFact.amount)).label('total'),
                func.avg(func.abs(TxnFact.amount)).label('avg_amount')
            ).filter(
                TxnFact.user_id == user_uuid,
                TxnFact.txn_date >= start_date.date() if isinstance(start_date, datetime) else start_date,
                TxnFact.txn_date <= end_date.date() if isinstance(end_date, datetime) else end_date,
                TxnFact.direction == "debit",
                TxnFact.merchant_name_norm.isnot(None)
            ).group_by(TxnFact.merchant_name_norm).having(
                func.count(TxnFact.txn_id) >= 3,  # At least 3 transactions
                func.avg(func.abs(TxnFact.amount)) < threshold  # But each is below threshold
            ).order_by(func.count(TxnFact.txn_id).desc()).limit(10).all()
        except Exception as e:
            print(f"⚠️  Database query error in leaks: {str(e)}")
            return {
                "period": period,
                "total_leak_amount": 0.0,
                "leaks_detected": 0,
                "leaks": []
            }
        
        leaks = []
        total_leak = 0.0
        
        for row in result:
            leak_amount = float(row.total)
            total_leak += leak_amount
            leaks.append({
                "merchant": row.merchant_name_norm or "Unknown",
                "transaction_count": row.count,
                "total_spent": leak_amount,
                "avg_transaction": round(float(row.avg_amount), 2),
                "leak_score": round(leak_amount / threshold, 2)
            })
        
        return {
            "period": period,
            "total_leak_amount": round(total_leak, 2),
            "leaks_detected": len(leaks),
            "leaks": leaks
        }
    finally:
        session.close()


@router.get("/comparing-periods")
async def compare_periods(
    user: UserDep = Depends(get_current_user)
):
    """
    Compare spending across different time periods
    """
    session = SessionLocal()
    
    try:
        now = datetime.utcnow()
        
        # Define periods
        periods = {
            "last_week": (now - timedelta(days=14), now - timedelta(days=7)),
            "this_week": (now - timedelta(days=7), now),
            "last_month": (now - timedelta(days=60), now - timedelta(days=30)),
            "this_month": (now - timedelta(days=30), now)
        }
        
        user_uuid = uuid.UUID(user.user_id) if isinstance(user.user_id, str) else user.user_id
        comparison = {}
        
        try:
            for period_name, (start, end) in periods.items():
                result = session.query(
                    func.sum(func.abs(TxnFact.amount)).label('total')
                ).filter(
                    TxnFact.user_id == user_uuid,
                    TxnFact.txn_date >= start.date() if isinstance(start, datetime) else start,
                    TxnFact.txn_date < end.date() if isinstance(end, datetime) else end,
                    TxnFact.direction == "debit"
                ).scalar()
                
                comparison[period_name] = float(result) if result else 0.0
        except Exception as e:
            print(f"⚠️  Database query error in comparing-periods: {str(e)}")
            comparison = {
                "last_week": 0.0,
                "this_week": 0.0,
                "last_month": 0.0,
                "this_month": 0.0
            }
        
        # Calculate changes
        if comparison.get("last_week", 0) > 0:
            week_change = ((comparison["this_week"] - comparison["last_week"]) / comparison["last_week"]) * 100
        else:
            week_change = 0
        
        if comparison.get("last_month", 0) > 0:
            month_change = ((comparison["this_month"] - comparison["last_month"]) / comparison["last_month"]) * 100
        else:
            month_change = 0
        
        return {
            "comparison": comparison,
            "week_change_percentage": round(week_change, 2),
            "month_change_percentage": round(month_change, 2)
        }
    finally:
        session.close()

