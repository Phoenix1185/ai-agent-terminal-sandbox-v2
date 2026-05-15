"""
Dynamic Tool Installer Service
Allows AI agents to install any tool/package on-demand.
Supports: pip, npm, apt, cargo, gem, go, and custom installations.
"""

import os
import subprocess
import shutil
import json
from typing import Dict, List, Optional, Literal
from pathlib import Path

from app.core.config import settings


class ToolInstaller:
    """Manages dynamic installation of tools and packages"""

    def __init__(self):
        self.tools_dir = Path(settings.TOOLS_DIR)
        self.tools_dir.mkdir(parents=True, exist_ok=True)
        self.installed_tools: Dict[str, dict] = self._load_tool_registry()

        # Package manager configurations
        self.managers = {
            "pip": {
                "install": ["pip", "install", "--user", "--quiet"],
                "uninstall": ["pip", "uninstall", "-y"],
                "list": ["pip", "list", "--format=json"],
                "check": ["python", "-c", "import {package}"]
            },
            "npm": {
                "install": ["npm", "install", "-g", "--quiet"],
                "uninstall": ["npm", "uninstall", "-g"],
                "list": ["npm", "list", "-g", "--json"],
                "check": ["which", "{package}"]
            },
            "apt": {
                "install": ["apt-get", "install", "-y", "--no-install-recommends"],
                "uninstall": ["apt-get", "remove", "-y"],
                "list": ["dpkg", "-l"],
                "check": ["which", "{package}"]
            },
            "cargo": {
                "install": ["cargo", "install", "--quiet"],
                "uninstall": ["cargo", "uninstall"],
                "list": ["cargo", "install", "--list"],
                "check": ["which", "{package}"]
            },
            "gem": {
                "install": ["gem", "install", "--no-document", "--quiet"],
                "uninstall": ["gem", "uninstall", "-a", "-x"],
                "list": ["gem", "list"],
                "check": ["which", "{package}"]
            },
            "go": {
                "install": ["go", "install"],
                "uninstall": None,  # Go doesn't have uninstall
                "list": ["go", "list", "-m", "all"],
                "check": ["which", "{package}"]
            },
            "conda": {
                "install": ["conda", "install", "-y"],
                "uninstall": ["conda", "remove", "-y"],
                "list": ["conda", "list", "--json"],
                "check": ["python", "-c", "import {package}"]
            }
        }

    def _load_tool_registry(self) -> Dict[str, dict]:
        """Load installed tools registry from disk"""
        registry_file = self.tools_dir / "registry.json"
        if registry_file.exists():
            with open(registry_file, "r") as f:
                return json.load(f)
        return {}

    def _save_tool_registry(self):
        """Save installed tools registry to disk"""
        registry_file = self.tools_dir / "registry.json"
        with open(registry_file, "w") as f:
            json.dump(self.installed_tools, f, indent=2)

    async def install(
        self,
        package: str,
        manager: Literal["pip", "npm", "apt", "cargo", "gem", "go", "conda", "auto"] = "auto",
        version: Optional[str] = None,
        force: bool = False
    ) -> dict:
        """
        Install a package using the specified package manager.

        Args:
            package: Package name or URL
            manager: Package manager to use (auto-detects if not specified)
            version: Specific version to install
            force: Reinstall even if already installed

        Returns:
            Installation result
        """

        # Auto-detect manager if not specified
        if manager == "auto":
            manager = self._detect_manager(package)

        if manager not in self.managers:
            return {
                "status": "error",
                "message": f"Unknown package manager: {manager}",
                "supported": list(self.managers.keys())
            }

        # Check if already installed
        if not force and self._is_installed(package, manager):
            return {
                "status": "already_installed",
                "package": package,
                "manager": manager,
                "info": self.installed_tools.get(package, {})
            }

        # Prepare install command
        config = self.managers[manager]
        cmd = config["install"].copy()

        if version:
            if manager == "pip":
                cmd.append(f"{package}=={version}")
            elif manager == "npm":
                cmd.append(f"{package}@{version}")
            else:
                cmd.append(package)
        else:
            cmd.append(package)

        # Execute installation
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                cwd=str(self.tools_dir)
            )

            success = result.returncode == 0

            if success:
                self.installed_tools[package] = {
                    "manager": manager,
                    "version": version or "latest",
                    "installed_at": __import__('time').time(),
                    "path": str(self.tools_dir)
                }
                self._save_tool_registry()

            return {
                "status": "installed" if success else "failed",
                "package": package,
                "manager": manager,
                "version": version,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }

        except subprocess.TimeoutExpired:
            return {
                "status": "timeout",
                "package": package,
                "message": "Installation timed out after 300 seconds"
            }
        except Exception as e:
            return {
                "status": "error",
                "package": package,
                "message": str(e)
            }

    async def uninstall(self, package: str, manager: Literal["pip", "npm", "apt", "cargo", "gem", "go", "conda"] = "auto") -> dict:
        """Uninstall a package"""

        if manager == "auto":
            manager = self._detect_manager(package)

        config = self.managers[manager]
        if not config["uninstall"]:
            return {
                "status": "error",
                "message": f"Uninstall not supported for {manager}"
            }

        cmd = config["uninstall"].copy()
        cmd.append(package)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.returncode == 0 and package in self.installed_tools:
                del self.installed_tools[package]
                self._save_tool_registry()

            return {
                "status": "uninstalled" if result.returncode == 0 else "failed",
                "package": package,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def list_installed(self, manager: Optional[str] = None) -> dict:
        """List installed packages"""

        if manager:
            if manager not in self.managers:
                return {"error": f"Unknown manager: {manager}"}

            config = self.managers[manager]
            try:
                result = subprocess.run(
                    config["list"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                return {
                    "manager": manager,
                    "packages": result.stdout
                }
            except Exception as e:
                return {"error": str(e)}

        # Return all from registry
        return {
            "installed_tools": self.installed_tools,
            "count": len(self.installed_tools)
        }

    def _detect_manager(self, package: str) -> str:
        """Auto-detect the best package manager for a package"""

        # Check if it's a Python package
        if package.startswith("python-") or package in ["requests", "numpy", "pandas", "flask", "django"]:
            return "pip"

        # Check if it's a Node package
        if package.startswith("@") or package in ["express", "lodash", "axios", "react"]:
            return "npm"

        # Check if it's a Rust package
        if package.startswith("cargo-"):
            return "cargo"

        # Check if it's a Ruby gem
        if package in ["rails", "sinatra", "jekyll"]:
            return "gem"

        # Default to pip for most AI tools
        return "pip"

    def _is_installed(self, package: str, manager: str) -> bool:
        """Check if a package is already installed"""

        if package in self.installed_tools:
            return True

        config = self.managers[manager]
        check_cmd = [c.format(package=package) for c in config["check"]]

        try:
            result = subprocess.run(
                check_cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except:
            return False

    async def install_from_url(self, url: str, name: Optional[str] = None) -> dict:
        """Install tool from a URL (GitHub, direct download, etc.)"""

        import tempfile
        import urllib.parse

        tool_name = name or urllib.parse.urlparse(url).path.split("/")[-1]
        install_dir = self.tools_dir / tool_name

        try:
            # Clone or download
            if url.endswith(".git"):
                result = subprocess.run(
                    ["git", "clone", "--depth", "1", url, str(install_dir)],
                    capture_output=True,
                    text=True,
                    timeout=120
                )
            else:
                # Download and extract
                with tempfile.NamedTemporaryFile() as tmp:
                    subprocess.run(
                        ["curl", "-L", "-o", tmp.name, url],
                        capture_output=True,
                        timeout=120
                    )
                    install_dir.mkdir(parents=True, exist_ok=True)
                    shutil.unpack_archive(tmp.name, str(install_dir))

            # Try to auto-install dependencies
            if (install_dir / "requirements.txt").exists():
                subprocess.run(
                    ["pip", "install", "-r", str(install_dir / "requirements.txt")],
                    capture_output=True,
                    timeout=120
                )

            if (install_dir / "package.json").exists():
                subprocess.run(
                    ["npm", "install"],
                    cwd=str(install_dir),
                    capture_output=True,
                    timeout=120
                )

            self.installed_tools[tool_name] = {
                "manager": "custom",
                "source": url,
                "path": str(install_dir),
                "installed_at": __import__('time').time()
            }
            self._save_tool_registry()

            return {
                "status": "installed",
                "tool": tool_name,
                "path": str(install_dir)
            }

        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def execute_tool(self, tool_name: str, args: List[str] = None) -> dict:
        """Execute an installed custom tool"""

        if tool_name not in self.installed_tools:
            return {"status": "error", "message": f"Tool '{tool_name}' not installed"}

        tool_info = self.installed_tools[tool_name]
        tool_path = Path(tool_info["path"])

        # Find executable
        executable = None
        for ext in ["", ".py", ".js", ".sh"]:
            candidate = tool_path / f"{tool_name}{ext}"
            if candidate.exists():
                executable = str(candidate)
                break

        if not executable:
            # Try to find any executable in the directory
            for file in tool_path.iterdir():
                if file.is_file() and os.access(file, os.X_OK):
                    executable = str(file)
                    break

        if not executable:
            return {"status": "error", "message": "No executable found for tool"}

        try:
            result = subprocess.run(
                [executable] + (args or []),
                capture_output=True,
                text=True,
                timeout=300,
                cwd=str(tool_path)
            )

            return {
                "status": "executed",
                "tool": tool_name,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}


# Global installer instance
tool_installer = ToolInstaller()
