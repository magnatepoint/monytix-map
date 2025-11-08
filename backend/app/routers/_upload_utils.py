"""
Upload utility helpers for file validation and streaming
"""
from fastapi import HTTPException, UploadFile
from typing import Tuple
import tempfile
import os
import logging

logger = logging.getLogger(__name__)

MAX_BYTES = 25 * 1024 * 1024  # 25MB

CSV_MIMES = {
    "text/csv",
    "text/plain",
    "application/csv",
    "application/vnd.ms-excel"
}

XLSX_MIMES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

XLS_MIMES = {
    "application/vnd.ms-excel",
}


async def save_upload_to_temp(upload: UploadFile, max_bytes: int = MAX_BYTES) -> Tuple[str, int, str]:
    """
    Stream UploadFile to a temp path, enforce size, and sniff mimetype.
    
    Returns:
        Tuple of (temp_file_path, file_size, detected_mime_type)
    """
    try:
        import magic
        sniff = magic.Magic(mime=True)
    except ImportError:
        # Fallback to content-type if python-magic not available
        logger.warning("python-magic not installed, using content-type header")
        sniff = None
    
    size = 0
    suffix = os.path.splitext(upload.filename or "")[1] or ""
    fd, path = tempfile.mkstemp(prefix="upload_", suffix=suffix)
    
    try:
        with os.fdopen(fd, "wb") as out:
            while True:
                chunk = await upload.read(1024 * 1024)  # Read 1MB chunks
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    try:
                        os.remove(path)
                    except Exception:
                        pass
                    raise HTTPException(status_code=413, detail="File too large (max 25MB)")
                out.write(chunk)
        
        # Sniff by content if magic available
        if sniff:
            try:
                mime = sniff.from_file(path) or (upload.content_type or "")
            except Exception:
                mime = upload.content_type or ""
        else:
            mime = upload.content_type or ""
        
        return path, size, mime
    except HTTPException:
        raise
    except Exception as e:
        # Ensure cleanup on failure
        try:
            os.remove(path)
        except Exception:
            pass
        logger.exception("Error saving upload to temp file")
        raise HTTPException(status_code=500, detail="Error processing upload file")


def ensure_csv_mime(mime: str, filename: str = None):
    """Validate that file is CSV based on MIME type"""
    if mime not in CSV_MIMES:
        # Some CSVs come as octet-stream; allow heuristic relax if filename endswith .csv
        if filename and filename.lower().endswith(".csv") and mime in ("application/octet-stream", ""):
            return
        raise HTTPException(status_code=400, detail=f"File is not CSV (got {mime})")


def ensure_excel_mime(mime: str) -> str:
    """
    Validate that file is Excel based on MIME type.
    
    Returns:
        "xlsx" or "xls"
    """
    if mime in XLSX_MIMES:
        return "xlsx"
    if mime in XLS_MIMES:
        return "xls"
    raise HTTPException(status_code=400, detail=f"File is not Excel (got {mime})")

