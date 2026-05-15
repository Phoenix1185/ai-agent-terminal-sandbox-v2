"""
AI Agent Terminal & Sandbox v2.0
With Fly.io volumes, dynamic tool installation, persistent sessions,
and multi-machine API key consistency.
"""

import asyncio
import json
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

from app.core.config import settings
from app.core.database import init_db, get_db
from app.core.security import verify_api_key
from app.api.routes import terminal, sandbox, browser, files, tools, system, installer, api_keys
from app.websocket.terminal_ws import TerminalWebSocketManager
from app.websocket.browser_ws import BrowserWebSocketManager
from app.core.monitoring import setup_monitoring
from app.core.celery_app import celery_app
from app.services.tool_installer import tool_installer
from app.services.api_key_manager import api_key_manager

# WebSocket managers
terminal_manager = TerminalWebSocketManager()
browser_manager = BrowserWebSocketManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler with volume setup"""
    # Startup
    await init_db()
    setup_monitoring()

    # Ensure volume directories exist
    for dir_path in [settings.SANDBOX_DIR, settings.SESSIONS_DIR, 
                     settings.TOOLS_DIR, settings.LOGS_DIR, settings.BACKUPS_DIR]:
        os.makedirs(dir_path, exist_ok=True)

    # Sync API keys from environment
    api_key_manager.sync_from_env()

    # Load persisted sessions if enabled
    if settings.PERSIST_SESSIONS:
        await terminal_manager.load_sessions()

    print("🚀 AI Agent Terminal & Sandbox v2.0 started!")
    print(f"   Environment: {settings.APP_ENV}")
    print(f"   Volume Path: {settings.VOLUME_PATH}")
    print(f"   Sandbox Dir: {settings.SANDBOX_DIR}")
    print(f"   Sessions Dir: {settings.SESSIONS_DIR}")
    print(f"   Tools Dir: {settings.TOOLS_DIR}")
    print(f"   API Keys: {len(api_key_manager.keys)} keys loaded")
    print(f"   Region: {settings.FLY_REGION or 'local'}")
    print(f"   Max Sessions: {settings.MAX_CONCURRENT_SESSIONS}")
    print(f"   Auto-install: {settings.AUTO_INSTALL_TOOLS}")

    yield

    # Shutdown
    if settings.PERSIST_SESSIONS:
        await terminal_manager.save_sessions()

    await terminal_manager.disconnect_all()
    await browser_manager.disconnect_all()
    print("👋 Shutting down...")


app = FastAPI(
    title="AI Agent Terminal & Sandbox",
    description="""
    A universal execution environment for AI agents with persistent storage.

    ## Features
    - **Terminal**: Full Linux shell access via WebSocket with session persistence
    - **Browser**: Playwright/Selenium automation sandbox
    - **Code Execution**: Python/Node.js/Bash sandboxed execution
    - **File System**: Full file management with Fly.io volume persistence
    - **Tool Installer**: Dynamic installation of any package/tool
    - **Tool Registry**: Extensible plugin system
    - **Multi-Machine**: Distributed across Fly.io regions with volumes
    - **API Key Management**: Volume-backed keys shared across all machines

    ## Authentication
    All endpoints require API key authentication via `X-API-Key` header.

    ## Volumes
    Data persists across restarts via Fly.io volumes mounted at `/data`.
    API keys are stored on the volume and shared across all machines.
    """,
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Include routers
app.include_router(terminal.router, prefix="/api/v1/terminal", tags=["Terminal"])
app.include_router(sandbox.router, prefix="/api/v1/sandbox", tags=["Sandbox"])
app.include_router(browser.router, prefix="/api/v1/browser", tags=["Browser"])
app.include_router(files.router, prefix="/api/v1/files", tags=["Files"])
app.include_router(tools.router, prefix="/api/v1/tools", tags=["Tools"])
app.include_router(system.router, prefix="/api/v1/system", tags=["System"])
app.include_router(installer.router, prefix="/api/v1/installer", tags=["Installer"])
app.include_router(api_keys.router, prefix="/api/v1/keys", tags=["API Keys"])


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main dashboard"""
    with open("app/templates/dashboard.html", "r") as f:
        return f.read()


@app.get("/health")
async def health_check():
    """Health check endpoint with volume and key info"""
    import psutil

    # Check volume availability
    volume_available = os.path.exists(settings.VOLUME_PATH)
    volume_usage = None
    if volume_available:
        try:
            usage = psutil.disk_usage(settings.VOLUME_PATH)
            volume_usage = {
                "total_gb": round(usage.total / (1024**3), 2),
                "used_gb": round(usage.used / (1024**3), 2),
                "free_gb": round(usage.free / (1024**3), 2),
                "percent": usage.percent
            }
        except:
            pass

    return {
        "status": "healthy",
        "version": "2.0.0",
        "cpu_percent": psutil.cpu_percent(),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_usage": psutil.disk_usage('/').percent,
        "active_sessions": len(terminal_manager.active_sessions),
        "machine_region": settings.FLY_REGION or "local",
        "api_keys_loaded": len(api_key_manager.keys),
        "volume": {
            "mounted": volume_available,
            "path": settings.VOLUME_PATH,
            "usage": volume_usage
        }
    }


@app.get("/api/v1/info")
async def get_info(api_key: str = Depends(verify_api_key)):
    """Get system information and capabilities"""

    installed_tools = len(tool_installer.installed_tools)

    return {
        "name": "AI Agent Terminal & Sandbox",
        "version": "2.0.0",
        "environment": settings.APP_ENV,
        "region": settings.FLY_REGION or "local",
        "volume_path": settings.VOLUME_PATH,
        "api_keys": {
            "total": len(api_key_manager.keys),
            "storage": "volume-backed (shared across machines)"
        },
        "capabilities": {
            "terminal": True,
            "browser": True,
            "code_execution": True,
            "file_system": True,
            "tool_registry": True,
            "tool_installation": True,
            "screenshots": True,
            "downloads": True,
            "multi_machine": True,
            "volume_persistence": True,
            "session_persistence": settings.PERSIST_SESSIONS,
            "api_key_management": True
        },
        "limits": {
            "max_concurrent_sessions": settings.MAX_CONCURRENT_SESSIONS,
            "sandbox_timeout": settings.SANDBOX_TIMEOUT,
            "max_file_size": settings.MAX_FILE_SIZE,
            "allowed_languages": ["python", "javascript", "bash", "sh", "ruby", "go", "rust"],
            "package_managers": ["pip", "npm", "apt", "cargo", "gem", "go", "conda"]
        },
        "installed_tools": installed_tools,
        "storage": {
            "sandbox": settings.SANDBOX_DIR,
            "sessions": settings.SESSIONS_DIR,
            "tools": settings.TOOLS_DIR,
            "logs": settings.LOGS_DIR,
            "backups": settings.BACKUPS_DIR,
            "api_keys": str(api_key_manager.keys_dir)
        }
    }


# WebSocket endpoints
@app.websocket("/ws/terminal")
async def terminal_websocket(websocket: WebSocket):
    """WebSocket for terminal sessions"""
    await terminal_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            await terminal_manager.handle_message(websocket, message)
    except WebSocketDisconnect:
        await terminal_manager.disconnect(websocket)
    except Exception as e:
        await terminal_manager.send_error(websocket, str(e))
        await terminal_manager.disconnect(websocket)


@app.websocket("/ws/browser")
async def browser_websocket(websocket: WebSocket):
    """WebSocket for browser automation sessions"""
    await browser_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            await browser_manager.handle_message(websocket, message)
    except WebSocketDisconnect:
        await browser_manager.disconnect(websocket)
    except Exception as e:
        await browser_manager.send_error(websocket, str(e))
        await browser_manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
