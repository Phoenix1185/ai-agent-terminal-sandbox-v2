"""System API with volume management"""

import os
import psutil
import platform
import shutil
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional

from app.core.config import settings
from app.core.security import verify_api_key

router = APIRouter()


@router.get("/status")
async def system_status(api_key: str = Depends(verify_api_key)):
    """Get comprehensive system status with volume info"""

    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    cpu_freq = psutil.cpu_freq()

    # Volume info
    volume_info = {}
    if os.path.exists(settings.VOLUME_PATH):
        try:
            vol_usage = psutil.disk_usage(settings.VOLUME_PATH)
            volume_info = {
                "path": settings.VOLUME_PATH,
                "total_gb": round(vol_usage.total / (1024**3), 2),
                "used_gb": round(vol_usage.used / (1024**3), 2),
                "free_gb": round(vol_usage.free / (1024**3), 2),
                "percent": vol_usage.percent
            }
        except:
            pass

    return {
        "status": "operational",
        "timestamp": __import__('time').time(),
        "machine": {
            "region": settings.FLY_REGION or "local",
            "allocation_id": settings.FLY_ALLOC_ID or "local",
            "platform": platform.platform(),
            "processor": platform.processor(),
            "python_version": platform.python_version()
        },
        "resources": {
            "cpu": {
                "percent": psutil.cpu_percent(interval=1),
                "count": psutil.cpu_count(),
                "frequency_mhz": cpu_freq.current if cpu_freq else None
            },
            "memory": {
                "total_gb": round(memory.total / (1024**3), 2),
                "available_gb": round(memory.available / (1024**3), 2),
                "percent": memory.percent,
                "used_gb": round(memory.used / (1024**3), 2)
            },
            "disk": {
                "total_gb": round(disk.total / (1024**3), 2),
                "free_gb": round(disk.free / (1024**3), 2),
                "percent": disk.percent
            },
            "volume": volume_info
        },
        "processes": len(psutil.pids()),
        "active_sessions": 0,
        "uptime": __import__('time').time() - psutil.boot_time()
    }


@router.get("/logs")
async def get_logs(
    lines: int = 100,
    service: Optional[str] = "app",
    api_key: str = Depends(verify_api_key)
):
    """Get application logs"""

    log_files = {
        "app": f"{settings.LOGS_DIR}/app.log",
        "system": "/var/log/syslog",
        "error": f"{settings.LOGS_DIR}/error.log",
        "install": f"{settings.LOGS_DIR}/install.log"
    }

    log_file = log_files.get(service, f"{settings.LOGS_DIR}/app.log")

    try:
        with open(log_file, "r") as f:
            all_lines = f.readlines()
            return {
                "service": service,
                "lines": lines,
                "logs": all_lines[-lines:] if len(all_lines) > lines else all_lines
            }
    except FileNotFoundError:
        return {
            "service": service,
            "lines": 0,
            "logs": ["Log file not found"]
        }


@router.post("/cleanup")
async def cleanup_system(api_key: str = Depends(verify_api_key)):
    """Clean up temporary files and resources"""

    import glob

    cleaned = 0
    freed_bytes = 0

    # Clean temp files
    temp_patterns = [
        "/tmp/sandbox/*",
        f"{settings.SANDBOX_DIR}/*.tmp",
        "/tmp/*.log",
        f"{settings.LOGS_DIR}/*.old"
    ]

    for pattern in temp_patterns:
        for file in glob.glob(pattern):
            try:
                if os.path.isfile(file):
                    freed_bytes += os.path.getsize(file)
                    os.remove(file)
                    cleaned += 1
                elif os.path.isdir(file):
                    freed_bytes += shutil.disk_usage(file).used
                    shutil.rmtree(file)
                    cleaned += 1
            except:
                pass

    return {
        "status": "cleaned",
        "files_removed": cleaned,
        "freed_mb": round(freed_bytes / (1024**2), 2)
    }


@router.post("/backup")
async def create_backup(api_key: str = Depends(verify_api_key)):
    """Create a backup of persistent data"""

    import tarfile
    import datetime

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"{settings.BACKUPS_DIR}/backup_{timestamp}.tar.gz"

    with tarfile.open(backup_file, "w:gz") as tar:
        for item in ["sandbox", "sessions", "tools"]:
            path = os.path.join(settings.VOLUME_PATH, item)
            if os.path.exists(path):
                tar.add(path, arcname=item)

    backup_size = os.path.getsize(backup_file)

    return {
        "status": "backed_up",
        "file": backup_file,
        "size_mb": round(backup_size / (1024**2), 2),
        "timestamp": timestamp
    }


@router.get("/backups")
async def list_backups(api_key: str = Depends(verify_api_key)):
    """List available backups"""

    backups = []
    if os.path.exists(settings.BACKUPS_DIR):
        for file in os.listdir(settings.BACKUPS_DIR):
            if file.startswith("backup_") and file.endswith(".tar.gz"):
                path = os.path.join(settings.BACKUPS_DIR, file)
                backups.append({
                    "file": file,
                    "size_mb": round(os.path.getsize(path) / (1024**2), 2),
                    "created": os.path.getctime(path)
                })

    return {
        "backups": sorted(backups, key=lambda x: x["created"], reverse=True),
        "count": len(backups)
    }


@router.post("/restore")
async def restore_backup(
    backup_file: str,
    api_key: str = Depends(verify_api_key)
):
    """Restore from a backup"""

    import tarfile

    backup_path = os.path.join(settings.BACKUPS_DIR, backup_file)

    if not os.path.exists(backup_path):
        raise HTTPException(404, "Backup file not found")

    with tarfile.open(backup_path, "r:gz") as tar:
        tar.extractall(settings.VOLUME_PATH)

    return {
        "status": "restored",
        "backup": backup_file,
        "restored_to": settings.VOLUME_PATH
    }
