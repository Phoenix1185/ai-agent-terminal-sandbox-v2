"""File System API with volume support"""

import os
import shutil
import mimetypes
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List
import aiofiles

from app.core.config import settings
from app.core.security import verify_api_key

router = APIRouter()


def safe_path(path: str) -> str:
    """Ensure path stays within sandbox or volume"""
    # Allow paths in sandbox or volume
    allowed_roots = [
        os.path.abspath(settings.SANDBOX_DIR),
        os.path.abspath(settings.VOLUME_PATH)
    ]

    if path.startswith("/"):
        full_path = os.path.abspath(path)
    else:
        full_path = os.path.abspath(os.path.join(settings.SANDBOX_DIR, path))

    for root in allowed_roots:
        if full_path.startswith(root):
            return full_path

    raise HTTPException(403, "Access denied: path outside allowed directories")


@router.get("/list")
async def list_files(
    path: str = "",
    api_key: str = Depends(verify_api_key)
):
    """List files in directory"""
    target_path = safe_path(path)

    if not os.path.exists(target_path):
        raise HTTPException(404, "Path not found")

    if os.path.isfile(target_path):
        stat = os.stat(target_path)
        return {
            "type": "file",
            "name": os.path.basename(target_path),
            "path": path,
            "size": stat.st_size,
            "modified": stat.st_mtime,
            "mime_type": mimetypes.guess_type(target_path)[0] or "application/octet-stream"
        }

    items = []
    for item in os.listdir(target_path):
        item_path = os.path.join(target_path, item)
        stat = os.stat(item_path)
        items.append({
            "name": item,
            "type": "directory" if os.path.isdir(item_path) else "file",
            "size": stat.st_size if os.path.isfile(item_path) else None,
            "modified": stat.st_mtime
        })

    return {
        "type": "directory",
        "path": path,
        "items": items
    }


@router.post("/upload")
async def upload_file(
    path: str = "",
    file: UploadFile = File(...),
    api_key: str = Depends(verify_api_key)
):
    """Upload file to sandbox"""
    target_path = safe_path(os.path.join(path, file.filename))

    os.makedirs(os.path.dirname(target_path), exist_ok=True)

    content = await file.read()
    if len(content) > settings.MAX_FILE_SIZE:
        raise HTTPException(413, "File too large")

    async with aiofiles.open(target_path, "wb") as f:
        await f.write(content)

    return {
        "status": "uploaded",
        "path": os.path.join(path, file.filename),
        "size": len(content)
    }


@router.get("/download")
async def download_file(
    path: str,
    api_key: str = Depends(verify_api_key)
):
    """Download file from sandbox"""
    target_path = safe_path(path)

    if not os.path.exists(target_path):
        raise HTTPException(404, "File not found")

    if os.path.isdir(target_path):
        import zipfile
        zip_path = f"{target_path}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(target_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, target_path)
                    zf.write(file_path, arcname)

        return FileResponse(
            zip_path,
            filename=f"{os.path.basename(path)}.zip",
            media_type="application/zip"
        )

    return FileResponse(
        target_path,
        filename=os.path.basename(path),
        media_type=mimetypes.guess_type(target_path)[0] or "application/octet-stream"
    )


@router.delete("/delete")
async def delete_file(
    path: str,
    api_key: str = Depends(verify_api_key)
):
    """Delete file or directory"""
    target_path = safe_path(path)

    if not os.path.exists(target_path):
        raise HTTPException(404, "Path not found")

    if os.path.isdir(target_path):
        shutil.rmtree(target_path)
    else:
        os.remove(target_path)

    return {"status": "deleted", "path": path}


@router.post("/mkdir")
async def create_directory(
    path: str,
    api_key: str = Depends(verify_api_key)
):
    """Create directory"""
    target_path = safe_path(path)
    os.makedirs(target_path, exist_ok=True)
    return {"status": "created", "path": path}


@router.get("/read")
async def read_file(
    path: str,
    offset: int = 0,
    limit: int = 10000,
    api_key: str = Depends(verify_api_key)
):
    """Read file content"""
    target_path = safe_path(path)

    if not os.path.exists(target_path):
        raise HTTPException(404, "File not found")

    try:
        async with aiofiles.open(target_path, "r") as f:
            await f.seek(offset)
            content = await f.read(limit)

        return {
            "path": path,
            "content": content,
            "offset": offset,
            "size": len(content)
        }
    except UnicodeDecodeError:
        raise HTTPException(400, "File is not text-readable")


@router.post("/write")
async def write_file(
    path: str,
    content: str,
    append: bool = False,
    api_key: str = Depends(verify_api_key)
):
    """Write content to file"""
    target_path = safe_path(path)

    os.makedirs(os.path.dirname(target_path), exist_ok=True)

    mode = "a" if append else "w"
    async with aiofiles.open(target_path, mode) as f:
        await f.write(content)

    return {
        "status": "written",
        "path": path,
        "size": len(content)
    }


@router.post("/copy")
async def copy_file(
    source: str,
    destination: str,
    api_key: str = Depends(verify_api_key)
):
    """Copy file or directory"""
    src_path = safe_path(source)
    dst_path = safe_path(destination)

    if not os.path.exists(src_path):
        raise HTTPException(404, "Source not found")

    if os.path.isdir(src_path):
        shutil.copytree(src_path, dst_path)
    else:
        shutil.copy2(src_path, dst_path)

    return {"status": "copied", "source": source, "destination": destination}


@router.post("/move")
async def move_file(
    source: str,
    destination: str,
    api_key: str = Depends(verify_api_key)
):
    """Move file or directory"""
    src_path = safe_path(source)
    dst_path = safe_path(destination)

    if not os.path.exists(src_path):
        raise HTTPException(404, "Source not found")

    shutil.move(src_path, dst_path)

    return {"status": "moved", "source": source, "destination": destination}
