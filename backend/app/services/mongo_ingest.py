"""
MongoDB Ingest Service
Handles storing raw files and raw events in MongoDB
"""

from app.database.mongodb import get_mongo_db
from app.database.mongo_schemas import (
    create_raw_file_document,
    create_raw_event_document,
    compute_file_hash,
    compute_event_fingerprint,
)
from datetime import datetime
from bson import ObjectId
from typing import Optional, Dict, Any, List
import uuid


class MongoIngestService:
    """Service for ingesting raw data into MongoDB"""
    
    def __init__(self):
        self.db = get_mongo_db()
        self.raw_files = self.db["raw_files"]
        self.raw_events = self.db["raw_events"]
        self.upload_jobs = self.db["upload_jobs"]  # Keep for backward compat
    
    def ingest_file(
        self,
        user_id: str,
        source_type: str,  # "csv", "pdf", "email"
        file_name: str,
        file_content: bytes,
        content_type: str,
        job_id: str,
        storage_kind: str = "mongo",
        storage_url: Optional[str] = None,
    ) -> ObjectId:
        """
        Store raw file in MongoDB (metadata only, or GridFS)
        
        Returns:
            MongoDB ObjectId of raw_file document
        """
        # Check for duplicate by hash
        file_hash = compute_file_hash(file_content)
        existing = self.raw_files.find_one({"hash_sha256": file_hash, "user_id": user_id})
        
        if existing:
            print(f"⚠️  Duplicate file detected (hash: {file_hash[:16]}...), reusing existing")
            return existing["_id"]
        
        # Create raw_file document
        raw_file_doc = create_raw_file_document(
            user_id=user_id,
            source_type=source_type,
            file_name=file_name,
            file_content=file_content,
            content_type=content_type,
            job_id=job_id,
            storage_kind=storage_kind,
            storage_url=storage_url,
        )
        
        # Insert document
        result = self.raw_files.insert_one(raw_file_doc)
        file_id = result.inserted_id
        
        print(f"✅ Ingested raw_file: {file_id} ({source_type}, {len(file_content)} bytes)")
        return file_id
    
    def ingest_csv_raw_events(
        self,
        user_id: str,
        file_id: ObjectId,
        job_id: str,
        csv_rows: List[Dict[str, Any]],  # List of row dictionaries
    ) -> List[ObjectId]:
        """
        Create raw_event documents for each CSV row
        
        Args:
            user_id: User UUID
            file_id: MongoDB ObjectId of raw_file
            job_id: Upload job UUID
            csv_rows: List of dictionaries (one per CSV row)
        
        Returns:
            List of raw_event ObjectIds
        """
        raw_event_ids = []
        
        for idx, row in enumerate(csv_rows):
            try:
                # Compute fingerprint
                fingerprint = compute_event_fingerprint(
                    source_type="csv",
                    file_id=str(file_id),
                    csv_row=idx,
                    raw_content=str(sorted(row.items())),
                )
                
                # Check for duplicate
                existing = self.raw_events.find_one({"fingerprint": fingerprint})
                if existing:
                    print(f"⚠️  Skipping duplicate CSV row {idx} (fingerprint: {fingerprint[:16]}...)")
                    raw_event_ids.append(existing["_id"])
                    continue
                
                # Create raw_event document
                raw_event_doc = create_raw_event_document(
                    user_id=user_id,
                    source_type="csv",
                    job_id=job_id,
                    file_id=str(file_id),
                    csv_row=idx,
                    raw_row=row,
                )
                
                # Insert document
                result = self.raw_events.insert_one(raw_event_doc)
                raw_event_ids.append(result.inserted_id)
                
            except Exception as e:
                print(f"❌ Error ingesting CSV row {idx}: {e}")
                continue
        
        print(f"✅ Ingested {len(raw_event_ids)} raw_events from CSV")
        return raw_event_ids
    
    def ingest_email_raw_events(
        self,
        user_id: str,
        job_id: str,
        email_messages: List[Dict[str, Any]],  # List of email message dicts
    ) -> List[ObjectId]:
        """
        Create raw_event documents for each email message
        
        Args:
            user_id: User UUID
            job_id: Upload job UUID
            email_messages: List of email message dictionaries with 'id', 'body', 'subject', etc.
        
        Returns:
            List of raw_event ObjectIds
        """
        raw_event_ids = []
        
        for email_msg in email_messages:
            try:
                email_id = email_msg.get("id") or email_msg.get("message_id")
                email_body = email_msg.get("body", "")
                
                # Compute fingerprint
                fingerprint = compute_event_fingerprint(
                    source_type="email",
                    email_id=email_id,
                    raw_content=email_body[:200],
                )
                
                # Check for duplicate
                existing = self.raw_events.find_one({"fingerprint": fingerprint})
                if existing:
                    print(f"⚠️  Skipping duplicate email {email_id} (fingerprint: {fingerprint[:16]}...)")
                    raw_event_ids.append(existing["_id"])
                    continue
                
                # Create raw_event document
                raw_event_doc = create_raw_event_document(
                    user_id=user_id,
                    source_type="email",
                    job_id=job_id,
                    email_id=email_id,
                    raw_text=email_body,
                )
                
                # Insert document
                result = self.raw_events.insert_one(raw_event_doc)
                raw_event_ids.append(result.inserted_id)
                
            except Exception as e:
                print(f"❌ Error ingesting email {email_msg.get('id', 'unknown')}: {e}")
                continue
        
        print(f"✅ Ingested {len(raw_event_ids)} raw_events from emails")
        return raw_event_ids
    
    def ingest_pdf_raw_events(
        self,
        user_id: str,
        file_id: ObjectId,
        job_id: str,
        pdf_lines: List[Dict[str, Any]],  # List of {page, line_no, text}
    ) -> List[ObjectId]:
        """
        Create raw_event documents for each PDF line
        
        Args:
            user_id: User UUID
            file_id: MongoDB ObjectId of raw_file
            job_id: Upload job UUID
            pdf_lines: List of dictionaries with 'page', 'line_no', 'text'
        
        Returns:
            List of raw_event ObjectIds
        """
        raw_event_ids = []
        
        for line_data in pdf_lines:
            try:
                page = line_data.get("page", 0)
                line_no = line_data.get("line_no", 0)
                text = line_data.get("text", "")
                
                # Compute fingerprint
                fingerprint = compute_event_fingerprint(
                    source_type="pdf",
                    file_id=str(file_id),
                    raw_content=f"page:{page}:line:{line_no}:{text[:200]}",
                )
                
                # Check for duplicate
                existing = self.raw_events.find_one({"fingerprint": fingerprint})
                if existing:
                    print(f"⚠️  Skipping duplicate PDF line page {page}, line {line_no}")
                    raw_event_ids.append(existing["_id"])
                    continue
                
                # Create raw_event document
                raw_event_doc = create_raw_event_document(
                    user_id=user_id,
                    source_type="pdf",
                    job_id=job_id,
                    file_id=str(file_id),
                    pdf_page=page,
                    line_no=line_no,
                    raw_text=text,
                )
                
                # Insert document
                result = self.raw_events.insert_one(raw_event_doc)
                raw_event_ids.append(result.inserted_id)
                
            except Exception as e:
                print(f"❌ Error ingesting PDF line page {line_data.get('page')}, line {line_data.get('line_no')}: {e}")
                continue
        
        print(f"✅ Ingested {len(raw_event_ids)} raw_events from PDF")
        return raw_event_ids
    
    def mark_file_parsed(self, file_id: ObjectId):
        """Mark raw_file as parsed"""
        self.raw_files.update_one(
            {"_id": file_id},
            {"$set": {"status": "parsed"}}
        )
    
    def mark_file_error(self, file_id: ObjectId, error: str):
        """Mark raw_file as error"""
        self.raw_files.update_one(
            {"_id": file_id},
            {"$set": {"status": "error", "error": error}}
        )

