"""Dynamic Tool Installer API"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, Literal, List

from app.core.config import settings
from app.core.security import verify_api_key
from app.services.tool_installer import tool_installer

router = APIRouter()


class InstallRequest(BaseModel):
    package: str
    manager: Literal["pip", "npm", "apt", "cargo", "gem", "go", "conda", "auto"] = "auto"
    version: Optional[str] = None
    force: bool = False


class InstallFromUrlRequest(BaseModel):
    url: str
    name: Optional[str] = None


class ExecuteToolRequest(BaseModel):
    tool_name: str
    args: Optional[List[str]] = []


@router.post("/install")
async def install_package(
    request: InstallRequest,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(verify_api_key)
):
    """
    Install any package/tool dynamically.

    Supported managers:
    - **pip**: Python packages
    - **npm**: Node.js packages
    - **apt**: System packages (requires sudo)
    - **cargo**: Rust packages
    - **gem**: Ruby gems
    - **go**: Go packages
    - **conda**: Conda packages
    - **auto**: Auto-detect based on package name
    """

    if not settings.AUTO_INSTALL_TOOLS:
        raise HTTPException(403, "Auto-installation is disabled")

    result = await tool_installer.install(
        package=request.package,
        manager=request.manager,
        version=request.version,
        force=request.force
    )

    if result["status"] == "error":
        raise HTTPException(400, result.get("message", "Installation failed"))

    return result


@router.post("/install/batch")
async def install_batch(
    packages: List[InstallRequest],
    api_key: str = Depends(verify_api_key)
):
    """Install multiple packages at once"""

    if not settings.AUTO_INSTALL_TOOLS:
        raise HTTPException(403, "Auto-installation is disabled")

    results = []
    for pkg in packages:
        result = await tool_installer.install(
            package=pkg.package,
            manager=pkg.manager,
            version=pkg.version,
            force=pkg.force
        )
        results.append(result)

    return {
        "status": "completed",
        "results": results,
        "successful": sum(1 for r in results if r["status"] in ["installed", "already_installed"]),
        "failed": sum(1 for r in results if r["status"] in ["failed", "error", "timeout"])
    }


@router.post("/install/from-url")
async def install_from_url(
    request: InstallFromUrlRequest,
    api_key: str = Depends(verify_api_key)
):
    """Install tool from GitHub or direct URL"""

    if not settings.AUTO_INSTALL_TOOLS:
        raise HTTPException(403, "Auto-installation is disabled")

    result = await tool_installer.install_from_url(request.url, request.name)

    if result["status"] == "error":
        raise HTTPException(400, result.get("message", "Installation failed"))

    return result


@router.post("/uninstall")
async def uninstall_package(
    package: str,
    manager: Literal["pip", "npm", "apt", "cargo", "gem", "go", "conda", "auto"] = "auto",
    api_key: str = Depends(verify_api_key)
):
    """Uninstall a package"""

    result = await tool_installer.uninstall(package, manager)

    if result["status"] == "error":
        raise HTTPException(400, result.get("message", "Uninstall failed"))

    return result


@router.get("/list")
async def list_installed(
    manager: Optional[str] = None,
    api_key: str = Depends(verify_api_key)
):
    """List installed packages/tools"""

    return await tool_installer.list_installed(manager)


@router.get("/search")
async def search_package(
    query: str,
    manager: Literal["pip", "npm", "apt", "cargo", "gem", "go", "conda"] = "pip",
    api_key: str = Depends(verify_api_key)
):
    """Search for packages (limited support)"""

    if manager == "pip":
        try:
            import subprocess
            result = subprocess.run(
                ["pip", "search", query],
                capture_output=True,
                text=True,
                timeout=30
            )
            return {
                "manager": manager,
                "query": query,
                "results": result.stdout if result.returncode == 0 else result.stderr
            }
        except:
            # pip search is disabled, use alternative
            return {
                "manager": manager,
                "query": query,
                "note": "Use 'pip index versions <package>' or visit pypi.org",
                "install_command": f"pip install {query}"
            }

    elif manager == "npm":
        return {
            "manager": manager,
            "query": query,
            "search_url": f"https://www.npmjs.com/search?q={query}",
            "install_command": f"npm install -g {query}"
        }

    return {
        "manager": manager,
        "query": query,
        "message": "Search not implemented for this manager"
    }


@router.post("/execute")
async def execute_installed_tool(
    request: ExecuteToolRequest,
    api_key: str = Depends(verify_api_key)
):
    """Execute an installed custom tool"""

    result = await tool_installer.execute_tool(request.tool_name, request.args)

    if result["status"] == "error":
        raise HTTPException(400, result.get("message", "Execution failed"))

    return result


@router.get("/managers")
async def list_managers(api_key: str = Depends(verify_api_key)):
    """List available package managers and their status"""

    import shutil

    managers = {
        "pip": shutil.which("pip") is not None,
        "npm": shutil.which("npm") is not None,
        "apt": shutil.which("apt-get") is not None,
        "cargo": shutil.which("cargo") is not None,
        "gem": shutil.which("gem") is not None,
        "go": shutil.which("go") is not None,
        "conda": shutil.which("conda") is not None,
    }

    return {
        "managers": managers,
        "available": [k for k, v in managers.items() if v],
        "auto_install_enabled": settings.AUTO_INSTALL_TOOLS
    }
