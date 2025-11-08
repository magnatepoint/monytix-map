from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status, Form
from typing import List
import uuid
from app.routers.auth import get_current_user, UserDep
from app.schemas.transaction import TransactionType, TransactionStatus
from app.database.mongodb import get_mongo_db
from datetime import datetime

router = APIRouter()


@router.post("/pdf")
async def upload_pdf(
    file: UploadFile = File(...),
    bank: str = Form(None),
    password: str = Form(None),
    user: UserDep = Depends(get_current_user)
):
    """
    Upload PDF bank statement for parsing
    
    Supports password-protected PDFs
    """
    
    # Validate file
    if not file.filename.endswith('.pdf'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are allowed"
        )
    
    if file.size > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds 10MB limit"
        )
    
    # Read file content
    content = await file.read()
    
    # Check if password protected
    import PyPDF2
    is_encrypted = False
    try:
        pdf_reader = PyPDF2.PdfReader(content)
        is_encrypted = pdf_reader.is_encrypted
    except:
        pass
    
    if is_encrypted and not password:
        # Return error requiring password
        return {
            "status": "error",
            "message": "PDF is password protected",
            "requires_password": True,
            "file_name": file.filename,
            "bank": bank or "unknown"
        }
    
    # Queue PDF parsing job
    job_id = str(uuid.uuid4())
    
    # Store in MongoDB for processing
    db = get_mongo_db()
    uploads_collection = db["upload_jobs"]
    
    uploads_collection.insert_one({
        "_id": job_id,
        "user_id": user.user_id,
        "job_type": "pdf_parse",
        "status": "pending",
        "file_name": file.filename,
        "file_size": len(content),
        "is_password_protected": is_encrypted,
        "created_at": datetime.utcnow()
    })
    
    # Import here to avoid circular dependency
    from app.workers.pdf_worker import parse_pdf
    
    # Queue Celery task with password if provided
    result = parse_pdf.delay(
        user_id=user.user_id,
        source_id=job_id,
        file_content=content,
        bank=bank or "unknown",
        password=password
    )
    
    return {
        "message": "PDF upload queued successfully",
        "job_id": job_id,
        "celery_task_id": result.id,
        "file_name": file.filename,
        "bank": bank or "unknown",
        "is_encrypted": is_encrypted,
        "requires_password": is_encrypted and not password
    }


@router.post("/pdf/retry-with-password")
async def retry_pdf_with_password(
    job_id: str,
    password: str,
    user: UserDep = Depends(get_current_user)
):
    """
    Retry processing a password-protected PDF with the correct password
    """
    db = get_mongo_db()
    jobs_collection = db["upload_jobs"]
    
    # Get the job
    job = jobs_collection.find_one({
        "_id": job_id,
        "user_id": user.user_id
    })
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    if job.get("status") == "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job already completed"
        )
    
    # Get file content from storage (would need to implement)
    # For now, return instructions
    return {
        "message": "Please re-upload the PDF with password",
        "job_id": job_id,
        "instructions": "Use /api/upload/pdf with password parameter"
    }


@router.post("/csv")
async def upload_csv(
    file: UploadFile = File(...),
    user: UserDep = Depends(get_current_user)
):
    """Upload CSV bank statement for parsing"""
    
    # Validate file
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files are allowed"
        )
    
    if file.size > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds 10MB limit"
        )
    
    # Read file content
    content = await file.read()
    
    # Queue CSV parsing job
    job_id = str(uuid.uuid4())
    
    # Store in MongoDB
    db = get_mongo_db()
    uploads_collection = db["upload_jobs"]
    
    uploads_collection.insert_one({
        "_id": job_id,
        "user_id": user.user_id,
        "job_type": "csv_parse",
        "status": "pending",
        "file_name": file.filename,
        "file_size": len(content),
        # Note: file_content is passed directly to Celery task, not stored in MongoDB
        "created_at": datetime.utcnow()
    })
    
    # For MVP: Process synchronously (skip Celery for now)
    # TODO: Re-enable Celery when Redis/RabbitMQ is configured
    try:
        from app.workers.csv_worker import parse_csv
        
        # Call worker function directly (synchronous)
        result = parse_csv(
            user_id=user.user_id,
            source_id=job_id,
            file_content=content
        )
        
        if result.get("status") == "error":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "CSV processing failed")
            )
        # After staging, attempt to load to fact + enrichment (best-effort)
        try:
            from app.routers.etl import load_staging_for_user
            inserted = load_staging_for_user(user.user_id)
            print(f"✅ Loaded {inserted} transactions from staging to fact table")
        except Exception as load_err:
            import traceback
            print(f"⚠️  Warning: Failed to load staging to fact table: {str(load_err)}")
            print(traceback.format_exc())
            # Don't fail the upload - staging is still successful
            # The transactions can be loaded later manually
        
        return {
            "message": f"CSV processed: {result.get('count', 0)} transactions",
            "job_id": job_id,
            "file_name": file.filename,
            "count": result.get("count", 0),
            "upload_id": result.get("upload_id")
        }
    except Exception as e:
        # If worker import fails or processing fails, update job status
        try:
            db = get_mongo_db()
            uploads_collection = db["upload_jobs"]
            uploads_collection.update_one(
                {"_id": job_id},
                {"$set": {"status": "failed", "error": str(e), "failed_at": datetime.utcnow()}}
            )
        except:
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing CSV: {str(e)}"
        )


@router.get("/jobs/{job_id}")
async def get_job_status(
    job_id: str,
    user: UserDep = Depends(get_current_user)
):
    """Get status of upload/processing job"""
    
    db = get_mongo_db()
    jobs_collection = db["upload_jobs"]
    
    job = jobs_collection.find_one({
        "_id": job_id,
        "user_id": user.user_id
    })
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    return {
        "job_id": str(job["_id"]),
        "job_type": job.get("job_type"),
        "status": job.get("status"),
        "file_name": job.get("file_name"),
        "created_at": job.get("created_at").isoformat() if job.get("created_at") else None,
        "completed_at": job.get("completed_at").isoformat() if job.get("completed_at") else None,
        "error": job.get("error")
    }


@router.post("/xls")
async def upload_xls(
    file: UploadFile = File(...),
    user: UserDep = Depends(get_current_user)
):
    """Upload XLS/XLSX bank statement for parsing"""
    
    # Validate file extension
    file_ext = file.filename.lower()
    if not (file_ext.endswith('.xls') or file_ext.endswith('.xlsx')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only XLS or XLSX files are allowed"
        )
    
    if file.size > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds 10MB limit"
        )
    
    # Read file content
    content = await file.read()
    
    # Determine file extension
    ext = 'xlsx' if file_ext.endswith('.xlsx') else 'xls'
    
    # Queue XLS parsing job
    job_id = str(uuid.uuid4())
    
    # Store in MongoDB
    db = get_mongo_db()
    uploads_collection = db["upload_jobs"]
    
    uploads_collection.insert_one({
        "_id": job_id,
        "user_id": user.user_id,
        "job_type": "xls_parse",
        "status": "pending",
        "file_name": file.filename,
        "file_size": len(content),
        "created_at": datetime.utcnow()
    })
    
    try:
        from app.workers.xls_worker import parse_xls
        
        # Call worker function directly (synchronous)
        result = parse_xls(
            user_id=user.user_id,
            source_id=job_id,
            file_content=content,
            file_extension=ext
        )
        
        if result.get("status") == "error":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "XLS processing failed")
            )
        
        # After staging, attempt to load to fact + enrichment (best-effort)
        try:
            from app.routers.etl import load_staging_for_user
            inserted = load_staging_for_user(user.user_id)
            print(f"✅ Loaded {inserted} transactions from staging to fact table")
        except Exception as load_err:
            import traceback
            print(f"⚠️  Warning: Failed to load staging to fact table: {str(load_err)}")
            print(traceback.format_exc())
            # Don't fail the upload - staging is still successful
        
        return {
            "message": f"XLS processed: {result.get('count', 0)} transactions",
            "job_id": job_id,
            "file_name": file.filename,
            "count": result.get("count", 0),
            "upload_id": result.get("upload_id")
        }
    except Exception as e:
        # If worker import fails or processing fails, update job status
        try:
            db = get_mongo_db()
            uploads_collection = db["upload_jobs"]
            uploads_collection.update_one(
                {"_id": job_id},
                {"$set": {"status": "failed", "error": str(e), "failed_at": datetime.utcnow()}}
            )
        except:
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing XLS: {str(e)}"
        )


@router.post("/gmail")
async def ingest_gmail(
    user: UserDep = Depends(get_current_user)
):
    """Start Gmail email fetching for transaction ingestion"""
    
    # This would typically require OAuth tokens stored securely
    # For MVP, return instructions
    
    return {
        "message": "Gmail integration requires OAuth setup",
        "instructions": [
            "1. Configure Gmail API credentials",
            "2. Obtain OAuth token",
            "3. Call this endpoint with credentials"
        ],
        "note": "Gmail integration is not fully implemented in MVP"
    }

