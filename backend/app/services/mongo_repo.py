"""
MongoDB Repository
CRUD helpers for raw_files, raw_events, parsed_events, upload_jobs
With idempotent insert by unique keys
"""

from app.database.mongodb import get_mongo_db
from typing import Optional, Dict, Any, List
from bson import ObjectId
from datetime import datetime
from pymongo.errors import DuplicateKeyError


class MongoRepo:
    """Repository for MongoDB collections"""
    
    def __init__(self):
        self.db = get_mongo_db()
        self.raw_files = self.db["raw_files"]
        self.raw_events = self.db["raw_events"]
        self.parsed_events = self.db["parsed_events"]
        self.upload_jobs = self.db["upload_jobs"]
    
    # ============================================================================
    # raw_files
    # ============================================================================
    
    def insert_raw_file(self, doc: Dict[str, Any]) -> ObjectId:
        """Insert raw_file document (idempotent by hash_sha256)"""
        try:
            result = self.raw_files.insert_one(doc)
            return result.inserted_id
        except DuplicateKeyError:
            # Document with same hash already exists
            existing = self.raw_files.find_one({"hash_sha256": doc["hash_sha256"], "user_id": doc["user_id"]})
            if existing:
                return existing["_id"]
            raise
    
    def get_raw_file(self, file_id: ObjectId) -> Optional[Dict[str, Any]]:
        """Get raw_file by ID"""
        return self.raw_files.find_one({"_id": file_id})
    
    def update_raw_file_status(self, file_id: ObjectId, status: str, error: Optional[str] = None):
        """Update raw_file status"""
        update = {"$set": {"status": status}}
        if error:
            update["$set"]["error"] = error
        self.raw_files.update_one({"_id": file_id}, update)
    
    # ============================================================================
    # raw_events
    # ============================================================================
    
    def insert_raw_event(self, doc: Dict[str, Any]) -> ObjectId:
        """Insert raw_event document (idempotent by fingerprint)"""
        try:
            result = self.raw_events.insert_one(doc)
            return result.inserted_id
        except DuplicateKeyError:
            # Document with same fingerprint already exists
            existing = self.raw_events.find_one({"fingerprint": doc["fingerprint"]})
            if existing:
                return existing["_id"]
            raise
    
    def get_raw_events_ready(self, user_id: Optional[str] = None, source_type: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get raw_events with status='ready' (for parsing)"""
        query = {"status": "ready"}
        if user_id:
            query["user_id"] = user_id
        if source_type:
            query["source_type"] = source_type
        
        return list(self.raw_events.find(query).sort("created_at", 1).limit(limit))
    
    def mark_raw_events_parsed(self, event_ids: List[ObjectId]):
        """Mark raw_events as parsed (atomically)"""
        self.raw_events.update_many(
            {"_id": {"$in": event_ids}},
            {"$set": {"status": "parsed"}}
        )
    
    def mark_raw_event_error(self, event_id: ObjectId, error: str):
        """Mark raw_event as error"""
        self.raw_events.update_one(
            {"_id": event_id},
            {"$set": {"status": "error", "error": error}}
        )
    
    # ============================================================================
    # parsed_events
    # ============================================================================
    
    def insert_parsed_event(self, doc: Dict[str, Any]) -> ObjectId:
        """Insert parsed_event document (idempotent by dedupe_key)"""
        try:
            result = self.parsed_events.insert_one(doc)
            return result.inserted_id
        except DuplicateKeyError:
            # Document with same dedupe_key already exists
            existing = self.parsed_events.find_one({"dedupe_key": doc["dedupe_key"]})
            if existing:
                return existing["_id"]
            raise
    
    def get_parsed_events_by_status(
        self,
        status: str,
        user_id: Optional[str] = None,
        job_id: Optional[str] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """Get parsed_events by status (for cleaning/exporting)"""
        query = {"status": status}
        if user_id:
            query["user_id"] = user_id
        if job_id:
            query["job_id"] = job_id
        
        return list(self.parsed_events.find(query).sort("created_at", 1).limit(limit))
    
    def mark_parsed_events_exported(self, event_ids: List[ObjectId], pg_upload_id: str, pg_txn_ids: List[str]):
        """Mark parsed_events as exported (atomically)"""
        self.parsed_events.update_many(
            {"_id": {"$in": event_ids}},
            {
                "$set": {
                    "status": "exported",
                    "exported_at": datetime.utcnow(),
                    "pg_upload_id": pg_upload_id,
                    "pg_txn_ids": pg_txn_ids
                }
            }
        )
    
    def mark_parsed_event_error(self, event_id: ObjectId, error: str):
        """Mark parsed_event as error"""
        self.parsed_events.update_one(
            {"_id": event_id},
            {"$set": {"status": "error", "error": error}}
        )
    
    def reset_parsed_events_status(self, event_ids: List[ObjectId], new_status: str):
        """Reset parsed_events status (for reprocessing)"""
        self.parsed_events.update_many(
            {"_id": {"$in": event_ids}},
            {
                "$set": {"status": new_status},
                "$unset": {"exported_at": "", "pg_upload_id": "", "pg_txn_ids": ""}
            }
        )
    
    # ============================================================================
    # upload_jobs
    # ============================================================================
    
    def create_upload_job(
        self,
        user_id: str,
        job_type: str,
        file_name: Optional[str] = None,
        ingest_mode: str = "mongo_first",
        source_id: Optional[ObjectId] = None,
    ) -> str:
        """Create upload_jobs entry"""
        job_id = str(ObjectId())
        doc = {
            "_id": job_id,
            "user_id": user_id,
            "job_type": job_type,
            "file_name": file_name,
            "status": "pending",
            "ingest_mode": ingest_mode,
            "source_id": source_id,
            "created_at": datetime.utcnow(),
            "started_at": None,
            "completed_at": None,
            "error": None,
        }
        self.upload_jobs.insert_one(doc)
        return job_id
    
    def update_upload_job_status(self, job_id: str, status: str, error: Optional[str] = None):
        """Update upload_jobs status"""
        update = {"$set": {"status": status}}
        if status == "processing" and not update.get("started_at"):
            update["$set"]["started_at"] = datetime.utcnow()
        elif status in ["completed", "failed"]:
            update["$set"]["completed_at"] = datetime.utcnow()
        if error:
            update["$set"]["error"] = error
        
        self.upload_jobs.update_one({"_id": job_id}, update)
    
    def get_upload_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get upload_jobs entry"""
        return self.upload_jobs.find_one({"_id": job_id})
    
    # ============================================================================
    # Metrics / Health
    # ============================================================================
    
    def get_stage_counts(self, user_id: Optional[str] = None) -> Dict[str, int]:
        """Get counts by stage for observability"""
        user_filter = {"user_id": user_id} if user_id else {}
        
        return {
            "raw_files_stored": self.raw_files.count_documents({**user_filter, "status": "stored"}),
            "raw_files_parsed": self.raw_files.count_documents({**user_filter, "status": "parsed"}),
            "raw_files_error": self.raw_files.count_documents({**user_filter, "status": "error"}),
            "raw_events_ready": self.raw_events.count_documents({**user_filter, "status": "ready"}),
            "raw_events_parsed": self.raw_events.count_documents({**user_filter, "status": "parsed"}),
            "raw_events_error": self.raw_events.count_documents({**user_filter, "status": "error"}),
            "parsed_events_parsed": self.parsed_events.count_documents({**user_filter, "status": "parsed"}),
            "parsed_events_cleaned": self.parsed_events.count_documents({**user_filter, "status": "cleaned"}),
            "parsed_events_exported": self.parsed_events.count_documents({**user_filter, "status": "exported"}),
            "parsed_events_error": self.parsed_events.count_documents({**user_filter, "status": "error"}),
        }
    
    def get_last_errors(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get last N errors from all collections"""
        errors = []
        
        # From raw_files
        for doc in self.raw_files.find({"status": "error"}, {"_id": 1, "error": 1, "created_at": 1}).sort("created_at", -1).limit(limit):
            errors.append({"collection": "raw_files", **doc})
        
        # From raw_events
        for doc in self.raw_events.find({"status": "error"}, {"_id": 1, "error": 1, "created_at": 1}).sort("created_at", -1).limit(limit):
            errors.append({"collection": "raw_events", **doc})
        
        # From parsed_events
        for doc in self.parsed_events.find({"status": "error"}, {"_id": 1, "error": 1, "created_at": 1}).sort("created_at", -1).limit(limit):
            errors.append({"collection": "parsed_events", **doc})
        
        return sorted(errors, key=lambda x: x.get("created_at", datetime.min), reverse=True)[:limit]

