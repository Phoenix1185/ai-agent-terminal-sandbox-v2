"""Celery configuration for background tasks"""

from celery import Celery
from app.core.config import settings

# Configure Celery
celery_app = Celery(
    "ai_agent_terminal",
    broker=settings.REDIS_URL or "redis://localhost:6379/0",
    backend=settings.REDIS_URL or "redis://localhost:6379/0",
    include=["app.core.tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000
)


@celery_app.task(bind=True, max_retries=3)
def execute_long_running_task(self, command: str, timeout: int = 300):
    """Execute long-running command in background"""
    import subprocess
    try:
        result = subprocess.run(
            command.split(),
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=settings.SANDBOX_DIR
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }
    except subprocess.TimeoutExpired:
        self.retry(countdown=60)
    except Exception as exc:
        self.retry(exc=exc, countdown=30)


@celery_app.task(bind=True)
def install_tool_task(self, package: str, manager: str, version: str = None):
    """Install tool in background"""
    from app.services.tool_installer import tool_installer
    import asyncio
    return asyncio.run(tool_installer.install(package, manager, version))


@celery_app.task(bind=True)
def backup_volume_task(self):
    """Create volume backup"""
    import tarfile
    import datetime
    import os

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"{settings.BACKUPS_DIR}/backup_{timestamp}.tar.gz"

    os.makedirs(settings.BACKUPS_DIR, exist_ok=True)

    with tarfile.open(backup_file, "w:gz") as tar:
        for item in ["sandbox", "sessions", "tools"]:
            path = os.path.join(settings.VOLUME_PATH, item)
            if os.path.exists(path):
                tar.add(path, arcname=item)

    return {"backup_file": backup_file, "status": "completed"}
