import os
import re
import aiofiles
from fastapi import UploadFile
from app.core.config import settings
from app.core.exceptions import FileValidationError
import logging

logger = logging.getLogger("finragvault.utils.file")


def sanitize_filename(filename: str) -> str:
    """Sanitizes file names to completely eliminate directory traversal attacks.
    
    Args:
        filename (str): Original uploaded file name.
        
    Returns:
        str: Sanitized file name.
    """
    # Keep only base name, removing relative/absolute paths
    base = os.path.basename(filename)
    
    # Replace non-alphanumeric, dot, underscore, dash with underscores
    sanitized = re.sub(r"[^a-zA-Z0-9._-]", "_", base)
    
    # Strip double underscores or consecutive dots
    sanitized = re.sub(r"__+", "_", sanitized)
    sanitized = re.sub(r"\.+", ".", sanitized)
    
    if not sanitized or sanitized in [".", ".."]:
        sanitized = "unnamed_document"
        
    return sanitized


def validate_file_metadata(file: UploadFile) -> None:
    """Performs size limits, MIME type constraints, and extension checks before saving.
    
    Raises:
        FileValidationError: If verification checks fail.
    """
    filename = file.filename or ""
    
    # Extract extension
    ext = filename.split(".")[-1].lower() if "." in filename else ""
    
    # Verify Extension
    if ext not in settings.ALLOWED_EXTENSIONS:
        logger.warning(f"Rejected upload: invalid extension '.{ext}' in file '{filename}'")
        raise FileValidationError(
            f"File extension '.{ext}' is not supported. Allowed formats: {', '.join(settings.ALLOWED_EXTENSIONS)}"
        )
        
    # Verify Content Type MIME
    if file.content_type not in settings.ALLOWED_MIME_TYPES:
        logger.warning(f"Rejected upload: invalid MIME '{file.content_type}' in file '{filename}'")
        raise FileValidationError(
            f"MIME type '{file.content_type}' is not supported. Allowed types: {', '.join(settings.ALLOWED_MIME_TYPES)}"
        )


async def save_upload_file_chunked(file: UploadFile, destination_path: str) -> int:
    """Asynchronously streams incoming multipart bytes in 64KB blocks directly to disk.
    
    Avoids memory spikes and verifies overall file limits.
    
    Args:
        file (UploadFile): FastAPI uploaded file object.
        destination_path (str): Destination folder disk path.
        
    Returns:
        int: Total size in bytes written.
        
    Raises:
        FileValidationError: If size threshold is breached during transmission.
    """
    total_bytes_written = 0
    chunk_size = 65536  # 64 KB
    
    # Verify uploads directory exists
    os.makedirs(os.path.dirname(destination_path), exist_ok=True)
    
    try:
        async with aiofiles.open(destination_path, "wb") as buffer:
            while chunk := await file.read(chunk_size):
                # Monitor size limits dynamically
                total_bytes_written += len(chunk)
                if total_bytes_written > settings.MAX_UPLOAD_SIZE:
                    # Clean up partial write to avoid junk files
                    await buffer.close()
                    if os.path.exists(destination_path):
                        os.remove(destination_path)
                    logger.warning(f"Rejected upload: size limit exceeded > {settings.MAX_UPLOAD_SIZE} bytes")
                    raise FileValidationError(
                        f"File size exceeds maximum threshold of {settings.MAX_UPLOAD_SIZE // (1024 * 1024)}MB."
                    )
                await buffer.write(chunk)
                
        logger.info(f"Chunked write complete: '{file.filename}' -> '{destination_path}' ({total_bytes_written} bytes)")
        return total_bytes_written
        
    except Exception as exc:
        if not isinstance(exc, FileValidationError):
            # Clean up on generic write failure
            if os.path.exists(destination_path):
                os.remove(destination_path)
            logger.error(f"Failed chunked stream write: {str(exc)}", exc_info=True)
            raise FileValidationError("Operational file system write error occurred during upload.")
        raise exc
