"""API Key Management Routes"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List

from app.core.config import settings
from app.core.security import verify_api_key, generate_api_key
from app.services.api_key_manager import api_key_manager

router = APIRouter()


class CreateKeyRequest(BaseModel):
    name: str
    permissions: Optional[List[str]] = None
    expires_days: Optional[int] = None
    rate_limit: Optional[int] = 1000


class UpdatePermissionsRequest(BaseModel):
    permissions: List[str]


@router.post("/create")
async def create_api_key(
    request: CreateKeyRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    Create a new API key.

    The key is stored on the volume and is accessible from ALL machines.
    Make sure to copy the returned key - it won't be shown again!
    """
    new_key = api_key_manager.generate_key(
        name=request.name,
        permissions=request.permissions or ["*"],
        expires_days=request.expires_days,
        rate_limit=request.rate_limit
    )

    return {
        "status": "created",
        "key": new_key,
        "name": request.name,
        "warning": "Store this key securely - it won't be shown again!"
    }


@router.get("/list")
async def list_api_keys(
    api_key: str = Depends(verify_api_key)
):
    """List all API keys (hashes only, no sensitive data)"""
    return {
        "keys": api_key_manager.list_keys(),
        "count": len(api_key_manager.keys)
    }


@router.post("/revoke")
async def revoke_api_key(
    key_hash: str,
    api_key: str = Depends(verify_api_key)
):
    """Revoke an API key (disables it)"""
    if api_key_manager.revoke_key(key_hash):
        return {"status": "revoked", "hash": key_hash}
    raise HTTPException(404, "Key not found")


@router.delete("/delete")
async def delete_api_key(
    key_hash: str,
    api_key: str = Depends(verify_api_key)
):
    """Permanently delete an API key"""
    if api_key_manager.delete_key(key_hash):
        return {"status": "deleted", "hash": key_hash}
    raise HTTPException(404, "Key not found or cannot delete master key")


@router.post("/{key_hash}/permissions")
async def update_permissions(
    key_hash: str,
    request: UpdatePermissionsRequest,
    api_key: str = Depends(verify_api_key)
):
    """Update API key permissions"""
    if api_key_manager.update_permissions(key_hash, request.permissions):
        return {"status": "updated", "hash": key_hash, "permissions": request.permissions}
    raise HTTPException(404, "Key not found")


@router.post("/rotate-master")
async def rotate_master_key(
    api_key: str = Depends(verify_api_key)
):
    """
    Rotate the master API key.

    WARNING: This invalidates the current master key!
    All clients using the old key will need to update.
    """
    new_key = api_key_manager.rotate_master_key()

    return {
        "status": "rotated",
        "new_key": new_key,
        "warning": "Update all clients with the new master key immediately!"
    }


@router.get("/verify")
async def verify_key_status(
    check_key: str,
    api_key: str = Depends(verify_api_key)
):
    """Check if an API key is valid (useful for debugging)"""
    is_valid = api_key_manager.verify_key(check_key)

    if is_valid:
        key_hash = __import__('hashlib').sha256(check_key.encode()).hexdigest()
        info = api_key_manager.get_key_info(key_hash)
        return {
            "valid": True,
            "name": info.get("name") if info else "Unknown",
            "permissions": info.get("permissions") if info else [],
            "expires_at": info.get("expires_at") if info else None
        }

    return {"valid": False}
