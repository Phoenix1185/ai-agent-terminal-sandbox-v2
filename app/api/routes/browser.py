"""Browser Automation API"""

import base64
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, Literal

from app.core.config import settings
from app.core.security import verify_api_key

router = APIRouter()


class BrowserActionRequest(BaseModel):
    action: Literal["navigate", "click", "type", "screenshot", "content", "evaluate", "scroll", "wait"]
    url: Optional[str] = None
    selector: Optional[str] = None
    text: Optional[str] = None
    script: Optional[str] = None
    full_page: Optional[bool] = False
    wait_time: Optional[int] = 1


@router.post("/action")
async def browser_action(
    request: BrowserActionRequest,
    api_key: str = Depends(verify_api_key)
):
    """Execute browser action via Playwright"""

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=settings.BROWSER_HEADLESS,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
            )
            context = browser.new_context(
                viewport={"width": settings.BROWSER_VIEWPORT_WIDTH, "height": settings.BROWSER_VIEWPORT_HEIGHT}
            )
            page = context.new_page()

            result = {}

            if request.action == "navigate":
                page.goto(request.url or "about:blank", wait_until="networkidle")
                result = {"status": "navigated", "url": page.url, "title": page.title()}
            elif request.action == "click":
                page.click(request.selector)
                result = {"status": "clicked", "selector": request.selector}
            elif request.action == "type":
                page.fill(request.selector, request.text or "")
                result = {"status": "typed", "selector": request.selector}
            elif request.action == "screenshot":
                screenshot = page.screenshot(full_page=request.full_page)
                result = {"status": "screenshot", "data": base64.b64encode(screenshot).decode(), "format": "png"}
            elif request.action == "content":
                result = {"status": "content", "data": page.content()}
            elif request.action == "evaluate":
                eval_result = page.evaluate(request.script or "")
                result = {"status": "evaluated", "result": eval_result}
            elif request.action == "scroll":
                page.evaluate("window.scrollBy(0, window.innerHeight)")
                result = {"status": "scrolled"}
            elif request.action == "wait":
                page.wait_for_timeout(request.wait_time * 1000)
                result = {"status": "waited", "time": request.wait_time}

            browser.close()
            return result
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/screenshot")
async def take_screenshot(
    url: str,
    full_page: bool = False,
    api_key: str = Depends(verify_api_key)
):
    """Take screenshot of a webpage"""
    return await browser_action(
        BrowserActionRequest(action="screenshot", url=url, full_page=full_page),
        api_key
    )


@router.post("/scrape")
async def scrape_page(
    url: str,
    selectors: Optional[dict] = None,
    api_key: str = Depends(verify_api_key)
):
    """Scrape content from a webpage"""

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            page = browser.new_page()
            page.goto(url, wait_until="networkidle")

            result = {"url": page.url, "title": page.title(), "content": page.content()}

            if selectors:
                result["extracted"] = {}
                for name, selector in selectors.items():
                    elements = page.query_selector_all(selector)
                    result["extracted"][name] = [el.inner_text() for el in elements]

            browser.close()
            return result
    except Exception as e:
        raise HTTPException(500, str(e))
