"""Terminal API Routes"""

import subprocess
import shlex
import os
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List

from app.core.config import settings
from app.core.security import verify_api_key

router = APIRouter()


class CommandRequest(BaseModel):
    command: str
    cwd: Optional[str] = None
    timeout: Optional[int] = 60
    env: Optional[dict] = None


class CommandResponse(BaseModel):
    stdout: str
    stderr: str
    returncode: int
    execution_time: float


@router.post("/execute", response_model=CommandResponse)
async def execute_command(
    request: CommandRequest,
    api_key: str = Depends(verify_api_key)
):
    """Execute a single command and return output"""
    parts = shlex.split(request.command)
    if parts and parts[0] not in settings.ALLOWED_COMMANDS:
        raise HTTPException(400, f"Command '{parts[0]}' not allowed")

    try:
        import time
        start = time.time()

        result = subprocess.run(
            parts,
            cwd=request.cwd or settings.SANDBOX_DIR,
            capture_output=True,
            text=True,
            timeout=min(request.timeout, settings.SANDBOX_TIMEOUT),
            env={**dict(os.environ), **(request.env or {})} if request.env else None
        )

        execution_time = time.time() - start

        return CommandResponse(
            stdout=result.stdout,
            stderr=result.stderr,
            returncode=result.returncode,
            execution_time=round(execution_time, 3)
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(408, "Command execution timed out")
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/execute/batch")
async def execute_batch(
    commands: List[str],
    api_key: str = Depends(verify_api_key)
):
    """Execute multiple commands in sequence"""
    results = []
    for cmd in commands:
        try:
            parts = shlex.split(cmd)
            if parts and parts[0] not in settings.ALLOWED_COMMANDS:
                results.append({"command": cmd, "error": f"Command '{parts[0]}' not allowed"})
                continue

            result = subprocess.run(
                parts,
                cwd=settings.SANDBOX_DIR,
                capture_output=True,
                text=True,
                timeout=settings.SANDBOX_TIMEOUT
            )
            results.append({
                "command": cmd,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            })
        except Exception as e:
            results.append({"command": cmd, "error": str(e)})

    return {"results": results}


@router.get("/sessions")
async def list_sessions(api_key: str = Depends(verify_api_key)):
    """List active terminal sessions"""
    from app.main import terminal_manager
    return {
        "active_sessions": len(terminal_manager.active_sessions),
        "sessions": [
            {"session_id": sid, "cwd": session.cwd}
            for sid, session in terminal_manager.active_sessions.items()
        ]
    }
