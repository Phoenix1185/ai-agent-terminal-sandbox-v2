"""
Browser Automation WebSocket Manager
Handles real-time browser control via Playwright.
"""

import asyncio
import json
import base64
from typing import Dict, Optional
from fastapi import WebSocket

from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from app.core.config import settings
from app.core.security import verify_api_key_ws


class BrowserSession:
    """Represents an active browser session"""

    def __init__(self, session_id: str, websocket: WebSocket):
        self.session_id = session_id
        self.websocket = websocket
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.running = False

    async def start(self):
        """Start browser session"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=settings.BROWSER_HEADLESS,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
        )
        self.context = await self.browser.new_context(
            viewport={"width": settings.BROWSER_VIEWPORT_WIDTH, "height": settings.BROWSER_VIEWPORT_HEIGHT},
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        self.page = await self.context.new_page()
        self.running = True

    async def navigate(self, url: str):
        if self.page:
            await self.page.goto(url, wait_until="networkidle")
            return {"status": "navigated", "url": url}
        return {"status": "error", "message": "Browser not started"}

    async def click(self, selector: str):
        if self.page:
            await self.page.click(selector)
            return {"status": "clicked", "selector": selector}
        return {"status": "error", "message": "Browser not started"}

    async def type_text(self, selector: str, text: str):
        if self.page:
            await self.page.fill(selector, text)
            return {"status": "typed", "selector": selector}
        return {"status": "error", "message": "Browser not started"}

    async def screenshot(self, full_page: bool = False):
        if self.page:
            screenshot = await self.page.screenshot(full_page=full_page)
            return {"status": "screenshot", "data": base64.b64encode(screenshot).decode(), "format": "png"}
        return {"status": "error", "message": "Browser not started"}

    async def get_content(self):
        if self.page:
            content = await self.page.content()
            return {"status": "content", "data": content}
        return {"status": "error", "message": "Browser not started"}

    async def evaluate(self, script: str):
        if self.page:
            result = await self.page.evaluate(script)
            return {"status": "evaluated", "result": result}
        return {"status": "error", "message": "Browser not started"}

    async def close(self):
        self.running = False
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()


class BrowserWebSocketManager:
    """Manages browser automation WebSocket connections"""

    def __init__(self):
        self.active_sessions: Dict[str, BrowserSession] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        try:
            headers = dict(websocket.scope.get("headers", []))
            api_key = headers.get(b"x-api-key", b"").decode()
            if not verify_api_key_ws(api_key):
                await websocket.send_text(json.dumps({"type": "error", "data": "Invalid API key"}))
                await websocket.close(code=4001)
                return
        except Exception:
            pass

        session_id = f"browser_{id(websocket)}"
        session = BrowserSession(session_id, websocket)
        await session.start()
        self.active_sessions[session_id] = session

        await websocket.send_text(json.dumps({
            "type": "connected",
            "session_id": session_id,
            "viewport": {"width": settings.BROWSER_VIEWPORT_WIDTH, "height": settings.BROWSER_VIEWPORT_HEIGHT}
        }))

    async def disconnect(self, websocket: WebSocket):
        session_id = f"browser_{id(websocket)}"
        if session_id in self.active_sessions:
            await self.active_sessions[session_id].close()
            del self.active_sessions[session_id]

    async def disconnect_all(self):
        for session in list(self.active_sessions.values()):
            await session.close()
        self.active_sessions.clear()

    async def handle_message(self, websocket: WebSocket, message: dict):
        session_id = f"browser_{id(websocket)}"
        session = self.active_sessions.get(session_id)

        if not session:
            await websocket.send_text(json.dumps({"type": "error", "data": "Session not found"}))
            return

        msg_type = message.get("type")

        try:
            if msg_type == "navigate":
                result = await session.navigate(message.get("url", ""))
            elif msg_type == "click":
                result = await session.click(message.get("selector", ""))
            elif msg_type == "type":
                result = await session.type_text(message.get("selector", ""), message.get("text", ""))
            elif msg_type == "screenshot":
                result = await session.screenshot(message.get("full_page", False))
            elif msg_type == "content":
                result = await session.get_content()
            elif msg_type == "evaluate":
                result = await session.evaluate(message.get("script", ""))
            elif msg_type == "ping":
                result = {"type": "pong"}
            else:
                result = {"status": "error", "message": f"Unknown command: {msg_type}"}

            await websocket.send_text(json.dumps(result))
        except Exception as e:
            await websocket.send_text(json.dumps({"type": "error", "data": str(e)}))

    async def send_error(self, websocket: WebSocket, error: str):
        try:
            await websocket.send_text(json.dumps({"type": "error", "data": error}))
        except:
            pass
