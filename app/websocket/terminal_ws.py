"""
Terminal WebSocket Manager with Session Persistence
Handles real-time terminal sessions with volume-backed persistence.
"""

import asyncio
import json
import os
import pty
import select
import struct
import termios
import fcntl
import signal
import shlex
from typing import Dict, Optional
from fastapi import WebSocket
from pathlib import Path

from app.core.config import settings
from app.core.security import verify_api_key_ws
from app.services.tool_installer import tool_installer


class TerminalSession:
    """Represents an active terminal session with persistence"""

    def __init__(self, session_id: str, websocket: WebSocket):
        self.session_id = session_id
        self.websocket = websocket
        self.pid: Optional[int] = None
        self.fd: Optional[int] = None
        self.cwd = settings.SANDBOX_DIR
        self.env = os.environ.copy()
        self.env["HOME"] = settings.SANDBOX_DIR
        self.env["PS1"] = "\u@ai-agent:\w\$ "
        self.env["PATH"] = f"{settings.TOOLS_DIR}/bin:{self.env.get('PATH', '')}"
        self.running = False
        self.task: Optional[asyncio.Task] = None
        self.history: list = []
        self.created_at = __import__('time').time()

    async def start(self):
        """Start a new PTY session"""
        self.pid, self.fd = pty.fork()

        if self.pid == 0:
            # Child process
            os.chdir(self.cwd)
            os.execvpe("/bin/bash", ["bash", "--rcfile", "/etc/bash.bashrc", "-i"], self.env)
        else:
            # Parent process
            self.running = True
            self.task = asyncio.create_task(self._read_output())
            self.resize(80, 24)

    async def _read_output(self):
        """Read output from PTY and send to WebSocket"""
        while self.running:
            try:
                ready, _, _ = select.select([self.fd], [], [], 0.1)
                if ready:
                    data = os.read(self.fd, 4096)
                    if data:
                        text = data.decode("utf-8", errors="replace")
                        await self.websocket.send_text(json.dumps({
                            "type": "output",
                            "data": text
                        }))
                        self.history.append({"type": "output", "data": text, "time": __import__('time').time()})
                    else:
                        break
            except (OSError, IOError):
                break
            except Exception as e:
                await self.websocket.send_text(json.dumps({
                    "type": "error",
                    "data": str(e)
                }))
                break
        self.running = False

    def write(self, data: str):
        """Write data to PTY"""
        if self.fd and self.running:
            os.write(self.fd, data.encode())

    def resize(self, cols: int, rows: int):
        """Resize terminal"""
        if self.fd:
            size = struct.pack("HHHH", rows, cols, 0, 0)
            fcntl.ioctl(self.fd, termios.TIOCSWINSZ, size)

    def kill(self):
        """Kill the terminal session"""
        self.running = False
        if self.task:
            self.task.cancel()
        if self.pid:
            try:
                os.kill(self.pid, signal.SIGTERM)
                os.waitpid(self.pid, 0)
            except ProcessLookupError:
                pass
        if self.fd:
            os.close(self.fd)

    def to_dict(self) -> dict:
        """Serialize session for persistence"""
        return {
            "session_id": self.session_id,
            "cwd": self.cwd,
            "env": {k: v for k, v in self.env.items() if not k.startswith("_")},
            "history": self.history[-100:],  # Last 100 entries
            "created_at": self.created_at
        }

    @classmethod
    def from_dict(cls, data: dict, websocket: WebSocket):
        """Restore session from dict"""
        session = cls(data["session_id"], websocket)
        session.cwd = data.get("cwd", settings.SANDBOX_DIR)
        session.env.update(data.get("env", {}))
        session.history = data.get("history", [])
        return session


class TerminalWebSocketManager:
    """Manages all terminal WebSocket connections with persistence"""

    def __init__(self):
        self.active_sessions: Dict[str, TerminalSession] = {}
        self.sessions_file = Path(settings.SESSIONS_DIR) / "sessions.json"

    async def load_sessions(self):
        """Load persisted sessions from volume"""
        if not settings.PERSIST_SESSIONS:
            return

        if self.sessions_file.exists():
            try:
                with open(self.sessions_file, "r") as f:
                    data = json.load(f)
                print(f"📂 Loaded {len(data)} persisted sessions")
            except Exception as e:
                print(f"⚠️ Failed to load sessions: {e}")

    async def save_sessions(self):
        """Save sessions to volume for persistence"""
        if not settings.PERSIST_SESSIONS:
            return

        try:
            data = {sid: session.to_dict() for sid, session in self.active_sessions.items()}
            with open(self.sessions_file, "w") as f:
                json.dump(data, f, indent=2)
            print(f"💾 Saved {len(data)} sessions")
        except Exception as e:
            print(f"⚠️ Failed to save sessions: {e}")

    async def connect(self, websocket: WebSocket):
        """Accept new WebSocket connection"""
        await websocket.accept()

        # Verify API key
        try:
            headers = dict(websocket.scope.get("headers", []))
            api_key = headers.get(b"x-api-key", b"").decode()
            if not verify_api_key_ws(api_key):
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "data": "Invalid API key"
                }))
                await websocket.close(code=4001)
                return
        except Exception:
            pass

        session_id = f"term_{id(websocket)}"
        session = TerminalSession(session_id, websocket)
        await session.start()
        self.active_sessions[session_id] = session

        await websocket.send_text(json.dumps({
            "type": "connected",
            "session_id": session_id,
            "cwd": session.cwd,
            "features": {
                "auto_install": settings.AUTO_INSTALL_TOOLS,
                "persistence": settings.PERSIST_SESSIONS
            }
        }))

    async def disconnect(self, websocket: WebSocket):
        """Disconnect WebSocket and cleanup"""
        session_id = f"term_{id(websocket)}"
        if session_id in self.active_sessions:
            if settings.PERSIST_SESSIONS:
                await self.save_sessions()
            self.active_sessions[session_id].kill()
            del self.active_sessions[session_id]

    async def disconnect_all(self):
        """Disconnect all sessions"""
        if settings.PERSIST_SESSIONS:
            await self.save_sessions()
        for session in list(self.active_sessions.values()):
            session.kill()
        self.active_sessions.clear()

    async def handle_message(self, websocket: WebSocket, message: dict):
        """Handle incoming WebSocket message with auto-install"""
        session_id = f"term_{id(websocket)}"
        session = self.active_sessions.get(session_id)

        if not session:
            await websocket.send_text(json.dumps({
                "type": "error",
                "data": "Session not found"
            }))
            return

        msg_type = message.get("type")

        if msg_type == "input":
            data = message.get("data", "")
            session.write(data)

        elif msg_type == "resize":
            cols = message.get("cols", 80)
            rows = message.get("rows", 24)
            session.resize(cols, rows)

        elif msg_type == "command":
            cmd = message.get("data", "")
            parts = shlex.split(cmd)

            if parts:
                # Check if command is allowed
                if parts[0] not in settings.ALLOWED_COMMANDS:
                    # Try to auto-install if it's a package manager command
                    if settings.AUTO_INSTALL_TOOLS and parts[0] in ["pip", "npm", "apt", "cargo", "gem", "go"]:
                        await websocket.send_text(json.dumps({
                            "type": "info",
                            "data": f"⏳ Auto-installing package manager tools..."
                        }))
                    else:
                        await websocket.send_text(json.dumps({
                            "type": "error",
                            "data": f"Command '{parts[0]}' not allowed"
                        }))
                        return

                # Auto-install missing tools
                if settings.AUTO_INSTALL_TOOLS and len(parts) > 1:
                    await self._check_and_install_tool(parts[0], parts[1], websocket)

            session.write(cmd + "\n")

        elif msg_type == "install":
            # Direct tool installation request
            if settings.AUTO_INSTALL_TOOLS:
                package = message.get("package", "")
                manager = message.get("manager", "auto")
                result = await tool_installer.install(package, manager)
                await websocket.send_text(json.dumps({
                    "type": "install_result",
                    "data": result
                }))

        elif msg_type == "ping":
            await websocket.send_text(json.dumps({"type": "pong"}))

    async def _check_and_install_tool(self, manager: str, package: str, websocket: WebSocket):
        """Check if tool is installed and auto-install if missing"""
        if not tool_installer._is_installed(package, manager):
            await websocket.send_text(json.dumps({
                "type": "info",
                "data": f"⏳ Package '{package}' not found. Installing..."
            }))
            result = await tool_installer.install(package, manager)
            status = "✅" if result["status"] == "installed" else "❌"
            await websocket.send_text(json.dumps({
                "type": "info",
                "data": f"{status} {result.get('message', result['status'])}"
            }))

    async def send_error(self, websocket: WebSocket, error: str):
        """Send error message"""
        try:
            await websocket.send_text(json.dumps({
                "type": "error",
                "data": error
            }))
        except:
            pass
