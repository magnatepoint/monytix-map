"""
ETL Pipeline Service
Handles Extract, Transform, Load operations with staging tables
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from decimal import Decimal
from app.database.postgresql import sync_engine
from sqlalchemy.orm import sessionmaker
SessionLocal = sessionmaker(bind=sync_engine)
from app.models.staging_models import (
    UploadBatch, TransactionStaging, GmailConnection,
    BillReminder, EmailTransaction
)
from app.models.postgresql_models import Transaction
from app.services.categorization_engine import CategorizationEngine
from app.services.normalization import TransactionNormalizer
from app.services.enrichment import EnrichmentService
from sqlalchemy import func
import uuid
import re


class ETLPipeline:
    """
    Complete ETL Pipeline for transaction processing
    """
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.categorization_engine = CategorizationEngine(user_id)
    
    # ==================== EXTRACT ====================
    
    def create_upload_batch(self, upload_type: str, file_name: str = None, 
                           file_size: int = None, metadata: Dict = None) -> str:
        """
        Create a new upload batch record
        
        Returns batch_id
        """
        session = SessionLocal()
        try:
            batch_id = str(uuid.uuid4())
            
            batch = UploadBatch(
                id=batch_id,
                user_id=self.user_id,
                upload_type=upload_type,
                file_name=file_name,
                file_size=file_size,
                total_records=0,
                processed_records=0,
                failed_records=0,
                status='uploaded',
                metadata=metadata or {},
                created_at=datetime.utcnow()
            )
            
            session.add(batch)
            session.commit()
            return batch_id
        finally:
            session.close()
    
    def stage_transactions(self, transactions: List[Dict], batch_id: str) -> List[str]:
        """
        Stage raw transaction data for validation
        
        Returns list of staged transaction IDs
        """
        session = SessionLocal()
        staged_ids = []
        
        try:
            for idx, txn in enumerate(transactions):
                staged_id = str(uuid.uuid4())
                
                # Parse and validate
                parsed = self._parse_transaction_data(txn)
                
                staged_txn = TransactionStaging(
                    id=staged_id,
                    upload_batch_id=batch_id,
                    user_id=self.user_id,
                    raw_amount=str(txn.get('amount', '')),
                    amount=parsed.get('amount'),
                    currency=parsed.get('currency', 'INR'),
                    raw_date=str(txn.get('transaction_date', '')),
                    transaction_date=parsed.get('transaction_date'),
                    description=parsed.get('description', ''),
                    merchant=parsed.get('merchant'),
                    category=parsed.get('category'),
                    bank=parsed.get('bank'),
                    transaction_type=parsed.get('transaction_type'),
                    reference_id=parsed.get('reference_id'),
                    data_source=txn.get('source', 'manual'),
                    row_number=txn.get('row_number'),
                    validation_status='pending',
                    created_at=datetime.utcnow()
                )
                
                session.add(staged_txn)
                staged_ids.append(staged_id)
            
            session.commit()
            return staged_ids
        finally:
            session.close()
    
    # ==================== TRANSFORM ====================
    
    def validate_staged_transactions(self, batch_id: str) -> Dict[str, Any]:
        """
        Validate all staged transactions in a batch
        
        Returns validation summary
        """
        session = SessionLocal()
        valid_count = 0
        invalid_count = 0
        
        try:
            staged_txns = session.query(TransactionStaging).filter(
                TransactionStaging.upload_batch_id == batch_id,
                TransactionStaging.validation_status == 'pending'
            ).all()
            
            for txn in staged_txns:
                errors = self._validate_transaction(txn)
                
                if errors:
                    txn.validation_status = 'invalid'
                    txn.validation_errors = errors
                    txn.error_message = '; '.join(errors)
                    invalid_count += 1
                else:
                    txn.validation_status = 'valid'
                    valid_count += 1
            
            session.commit()
            
            return {
                "valid": valid_count,
                "invalid": invalid_count,
                "total": len(staged_txns)
            }
        finally:
            session.close()
    
    def categorize_staged_transactions(self, batch_id: str) -> Dict[str, Any]:
        """
        Apply categorization to valid staged transactions
        """
        session = SessionLocal()
        categorized_count = 0
        
        try:
            valid_txns = session.query(TransactionStaging).filter(
                TransactionStaging.upload_batch_id == batch_id,
                TransactionStaging.validation_status == 'valid',
                TransactionStaging.processing_status == 'pending'
            ).all()
            
            for txn in valid_txns:
                # Categorize
                category, confidence = self.categorization_engine.categorize(
                    txn.description,
                    txn.merchant,
                    txn.bank
                )
                
                # Detect transaction type
                txn_type = self.categorization_engine.detect_transaction_type(
                    txn.description,
                    Decimal(txn.amount)
                )
                
                txn.category = category
                txn.transaction_type = txn_type
                txn.confidence_score = confidence
                txn.processing_status = 'processing'
                
                categorized_count += 1
            
            session.commit()
            return {"categorized": categorized_count}
        finally:
            session.close()
    
    # ==================== LOAD ====================
    
    def load_to_production(self, batch_id: str) -> Dict[str, Any]:
        """
        Load validated and categorized transactions to production table (txn_fact)
        Includes normalization, deduplication, and content hashing
        """
        session = SessionLocal()
        loaded_count = 0
        failed_count = 0
        duplicate_count = 0
        
        try:
            # Get batch
            batch = session.query(UploadBatch).filter(
                UploadBatch.id == batch_id
            ).first()
            
            # Get transactions ready for loading
            ready_txns = session.query(TransactionStaging).filter(
                TransactionStaging.upload_batch_id == batch_id,
                TransactionStaging.validation_status == 'valid',
                TransactionStaging.processing_status == 'processing'
            ).all()
            
            # Initialize services
            normalizer = TransactionNormalizer(self.user_id)
            enrichment_service = EnrichmentService(self.user_id)
            
            # Collect all transactions for batch normalization
            transactions_to_load = []
            
            for staged_txn in ready_txns:
                # Convert to dict
                txn_dict = {
                    'amount': staged_txn.amount,
                    'currency': staged_txn.currency,
                    'transaction_date': staged_txn.transaction_date,
                    'description': staged_txn.description,
                    'merchant': staged_txn.merchant,
                    'category': staged_txn.category,
                    'bank': staged_txn.bank,
                    'transaction_type': staged_txn.transaction_type,
                    'reference_id': staged_txn.reference_id,
                    'subcategory': None
                }
                
                transactions_to_load.append(txn_dict)
            
            # Normalize all transactions
            normalized_txns = []
            for txn in transactions_to_load:
                normalized = normalizer.normalize_and_validate(txn)
                normalized_txns.append(normalized)
            
            # Deduplicate
            unique_txns, duplicate_hashes = normalizer.deduplicate(normalized_txns)
            duplicate_count = len(duplicate_hashes)
            
            # Load unique transactions
            for normalized_txn in unique_txns:
                load_result = normalizer.load_to_fact_table(normalized_txn)
                
                if load_result['success']:
                    loaded_count += 1
                    
                    # Apply enrichment to loaded transaction
                    try:
                        enrichment = enrichment_service.enrich_transaction(normalized_txn)
                        
                        # Get the transaction ID from load_result
                        txn_id = load_result.get('transaction_id')
                        if txn_id:
                            enrichment_service.save_enrichment(txn_id, enrichment)
                    except Exception as e:
                        print(f"Error enriching transaction: {e}")
                    
                    # Update staged record
                    for staged_txn in ready_txns:
                        if staged_txn.description == normalized_txn.get('raw_data', {}).get('description'):
                            staged_txn.processing_status = 'completed'
                            staged_txn.processed_at = datetime.utcnow()
                            break
                else:
                    failed_count += 1
                    
                    # Check if it's a duplicate
                    if 'Duplicate transaction' in load_result.get('error', ''):
                        duplicate_count += 1
                    else:
                        for staged_txn in ready_txns:
                            if staged_txn.description == normalized_txn.get('raw_data', {}).get('description'):
                                staged_txn.processing_status = 'failed'
                                staged_txn.error_at = datetime.utcnow()
                                staged_txn.error_message = load_result.get('error', 'Unknown error')
                                break
            
            # Update batch status
            batch.processed_records = loaded_count
            batch.failed_records = failed_count
            
            if loaded_count > 0:
                batch.status = 'completed' if failed_count == 0 and duplicate_count == 0 else 'partial'
                batch.completed_at = datetime.utcnow()
            
            session.commit()
            
            return {
                "loaded": loaded_count,
                "failed": failed_count,
                "duplicates_skipped": duplicate_count,
                "batch_status": batch.status
            }
        finally:
            session.close()
    
    # ==================== HELPER METHODS ====================
    
    def _parse_transaction_data(self, data: Dict) -> Dict:
        """Parse raw transaction data"""
        parsed = {}
        
        # Amount
        try:
            amount_str = str(data.get('amount', 0)).replace(',', '')
            parsed['amount'] = float(amount_str)
        except:
            parsed['amount'] = 0.0
        
        # Date
        try:
            date_str = data.get('transaction_date', '')
            # Try multiple formats
            for fmt in ['%Y-%m-%d', '%d-%m-%Y', '%Y-%m-%dT%H:%M:%S', '%d/%m/%Y']:
                try:
                    parsed['transaction_date'] = datetime.strptime(date_str, fmt)
                    break
                except:
                    continue
            else:
                parsed['transaction_date'] = datetime.utcnow()
        except:
            parsed['transaction_date'] = datetime.utcnow()
        
        # Description and other fields
        parsed['description'] = str(data.get('description', ''))
        parsed['merchant'] = data.get('merchant')
        parsed['bank'] = data.get('bank')
        parsed['reference_id'] = data.get('reference_id')
        parsed['currency'] = data.get('currency', 'INR')
        parsed['transaction_type'] = data.get('transaction_type', 'debit')
        
        return parsed
    
    def _validate_transaction(self, txn: TransactionStaging) -> List[str]:
        """Validate a transaction record"""
        errors = []
        
        # Amount validation
        if not txn.amount or txn.amount <= 0:
            errors.append("Invalid amount")
        
        # Date validation
        if not txn.transaction_date:
            errors.append("Invalid transaction date")
        
        # Description validation
        if not txn.description or len(txn.description.strip()) == 0:
            errors.append("Description is required")
        
        # Currency validation
        if txn.currency not in ['INR', 'USD', 'EUR']:
            errors.append("Unsupported currency")
        
        return errors
    
    def get_batch_status(self, batch_id: str) -> Dict[str, Any]:
        """Get status of an upload batch"""
        session = SessionLocal()
        try:
            batch = session.query(UploadBatch).filter(
                UploadBatch.id == batch_id,
                UploadBatch.user_id == self.user_id
            ).first()
            
            if not batch:
                return {"error": "Batch not found"}
            
            # Get staging statistics
            staged = session.query(func.count(TransactionStaging.id)).filter(
                TransactionStaging.upload_batch_id == batch_id
            ).scalar() or 0
            
            valid = session.query(func.count(TransactionStaging.id)).filter(
                TransactionStaging.upload_batch_id == batch_id,
                TransactionStaging.validation_status == 'valid'
            ).scalar() or 0
            
            invalid = session.query(func.count(TransactionStaging.id)).filter(
                TransactionStaging.upload_batch_id == batch_id,
                TransactionStaging.validation_status == 'invalid'
            ).scalar() or 0
            
            return {
                "batch_id": batch_id,
                "status": batch.status,
                "upload_type": batch.upload_type,
                "file_name": batch.file_name,
                "total_records": staged,
                "valid": valid,
                "invalid": invalid,
                "processed": batch.processed_records,
                "failed": batch.failed_records,
                "created_at": batch.created_at.isoformat() if batch.created_at else None,
                "completed_at": batch.completed_at.isoformat() if batch.completed_at else None
            }
        finally:
            session.close()

