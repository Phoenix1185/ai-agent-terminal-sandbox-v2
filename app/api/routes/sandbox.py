"""Code Execution Sandbox API"""

import os
import tempfile
import subprocess
import time
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Optional, Literal

from app.core.config import settings
from app.core.security import verify_api_key

router = APIRouter()


class CodeExecutionRequest(BaseModel):
    code: str
    language: Literal["python", "javascript", "bash", "ruby", "go"]
    timeout: Optional[int] = 30
    stdin: Optional[str] = None
    dependencies: Optional[list] = None


class CodeExecutionResponse(BaseModel):
    stdout: str
    stderr: str
    returncode: int
    execution_time: float
    language: str


@router.post("/execute", response_model=CodeExecutionResponse)
async def execute_code(
    request: CodeExecutionRequest,
    api_key: str = Depends(verify_api_key)
):
    """Execute code in sandboxed environment"""

    language_configs = {
        "python": {"extension": "py", "command": ["python3", "-u"]},
        "javascript": {"extension": "js", "command": ["node"]},
        "bash": {"extension": "sh", "command": ["bash"]},
        "ruby": {"extension": "rb", "command": ["ruby"]},
        "go": {"extension": "go", "command": ["go", "run"]}
    }

    config = language_configs.get(request.language)
    if not config:
        raise HTTPException(400, f"Unsupported language: {request.language}")

    with tempfile.NamedTemporaryFile(
        mode='w',
        suffix=f".{config['extension']}",
        dir=settings.SANDBOX_DIR,
        delete=False
    ) as f:
        f.write(request.code)
        temp_file = f.name

    try:
        start = time.time()

        if request.dependencies and request.language == "python":
            dep_cmd = ["pip", "install"] + request.dependencies
            subprocess.run(dep_cmd, capture_output=True, timeout=60)
        elif request.dependencies and request.language == "javascript":
            dep_cmd = ["npm", "install"] + request.dependencies
            subprocess.run(dep_cmd, capture_output=True, timeout=60, cwd=settings.SANDBOX_DIR)

        cmd = config["command"] + [temp_file]
        result = subprocess.run(
            cmd,
            cwd=settings.SANDBOX_DIR,
            capture_output=True,
            text=True,
            timeout=min(request.timeout, settings.SANDBOX_TIMEOUT),
            input=request.stdin
        )

        execution_time = time.time() - start

        return CodeExecutionResponse(
            stdout=result.stdout,
            stderr=result.stderr,
            returncode=result.returncode,
            execution_time=round(execution_time, 3),
            language=request.language
        )

    except subprocess.TimeoutExpired:
        raise HTTPException(408, "Code execution timed out")
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        try:
            os.remove(temp_file)
        except:
            pass


@router.post("/execute/file")
async def execute_file(
    file: UploadFile = File(...),
    language: Optional[str] = "auto",
    timeout: Optional[int] = 30,
    api_key: str = Depends(verify_api_key)
):
    """Upload and execute a code file"""

    if language == "auto":
        ext = file.filename.split(".")[-1].lower()
        lang_map = {"py": "python", "js": "javascript", "sh": "bash", "rb": "ruby", "go": "go"}
        language = lang_map.get(ext, "python")

    content = await file.read()
    code = content.decode("utf-8")

    return await execute_code(
        CodeExecutionRequest(code=code, language=language, timeout=timeout),
        api_key
    )
