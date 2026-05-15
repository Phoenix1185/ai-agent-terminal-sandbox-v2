"""Tool Registry API"""

import json
import os
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

from app.core.config import settings
from app.core.security import verify_api_key

router = APIRouter()

TOOL_REGISTRY: Dict[str, dict] = {}


class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any]
    endpoint: str
    method: str = "POST"
    auth_required: bool = True


class ToolExecutionRequest(BaseModel):
    tool_name: str
    parameters: Dict[str, Any]


@router.post("/register")
async def register_tool(
    tool: ToolDefinition,
    api_key: str = Depends(verify_api_key)
):
    """Register a new tool"""
    TOOL_REGISTRY[tool.name] = tool.dict()
    return {"status": "registered", "tool": tool.name, "registry_size": len(TOOL_REGISTRY)}


@router.get("/list")
async def list_tools(api_key: str = Depends(verify_api_key)):
    """List all registered tools"""
    return {"tools": list(TOOL_REGISTRY.values()), "count": len(TOOL_REGISTRY)}


@router.get("/{tool_name}")
async def get_tool(tool_name: str, api_key: str = Depends(verify_api_key)):
    """Get tool definition"""
    if tool_name not in TOOL_REGISTRY:
        raise HTTPException(404, "Tool not found")
    return TOOL_REGISTRY[tool_name]


@router.post("/execute")
async def execute_tool(
    request: ToolExecutionRequest,
    api_key: str = Depends(verify_api_key)
):
    """Execute a registered tool"""

    builtin_tools = {
        "web_search": _web_search,
        "calculator": _calculator,
        "file_analyzer": _file_analyzer,
        "system_info": _system_info,
        "git_clone": _git_clone,
        "npm_install": _npm_install,
        "pip_install": _pip_install
    }

    if request.tool_name in builtin_tools:
        return await builtin_tools[request.tool_name](request.parameters)

    if request.tool_name in TOOL_REGISTRY:
        return {"status": "executed", "tool": request.tool_name, "result": "External tool execution"}

    raise HTTPException(404, f"Tool '{request.tool_name}' not found")


async def _web_search(params: dict):
    query = params.get("query", "")
    import subprocess
    result = subprocess.run(
        ["curl", "-s", f"https://html.duckduckgo.com/html/?q={query}"],
        capture_output=True, text=True, timeout=30
    )
    return {"tool": "web_search", "query": query, "results": result.stdout[:5000]}


async def _calculator(params: dict):
    expression = params.get("expression", "")
    try:
        allowed_names = {"abs": abs, "max": max, "min": min, "sum": sum, "len": len, "round": round, "pow": pow}
        result = eval(expression, {"__builtins__": {}}, allowed_names)
        return {"tool": "calculator", "expression": expression, "result": result}
    except Exception as e:
        return {"tool": "calculator", "error": str(e)}


async def _file_analyzer(params: dict):
    path = params.get("path", "")
    target = os.path.join(settings.SANDBOX_DIR, path)
    if not os.path.exists(target):
        return {"tool": "file_analyzer", "error": "File not found"}
    stat = os.stat(target)
    return {"tool": "file_analyzer", "path": path, "size": stat.st_size, "modified": stat.st_mtime, "type": "directory" if os.path.isdir(target) else "file"}


async def _system_info(params: dict):
    import psutil
    return {"tool": "system_info", "cpu_percent": psutil.cpu_percent(), "memory": dict(psutil.virtual_memory()._asdict()), "disk": dict(psutil.disk_usage('/')._asdict()), "region": settings.FLY_REGION or "local"}


async def _git_clone(params: dict):
    url = params.get("url", "")
    path = params.get("path", "repo")
    import subprocess
    result = subprocess.run(["git", "clone", url, path], cwd=settings.SANDBOX_DIR, capture_output=True, text=True, timeout=120)
    return {"tool": "git_clone", "url": url, "path": path, "stdout": result.stdout, "stderr": result.stderr}


async def _npm_install(params: dict):
    packages = params.get("packages", [])
    path = params.get("path", ".")
    import subprocess
    result = subprocess.run(["npm", "install"] + packages, cwd=os.path.join(settings.SANDBOX_DIR, path), capture_output=True, text=True, timeout=120)
    return {"tool": "npm_install", "packages": packages, "stdout": result.stdout, "stderr": result.stderr}


async def _pip_install(params: dict):
    packages = params.get("packages", [])
    import subprocess
    result = subprocess.run(["pip", "install"] + packages, capture_output=True, text=True, timeout=120)
    return {"tool": "pip_install", "packages": packages, "stdout": result.stdout, "stderr": result.stderr}
