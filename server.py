#!/usr/bin/env python3
"""
Property Tax Scraper MCP Server
Provides browser automation tools for scraping assessor websites
"""

import asyncio
import json
import base64
from typing import Any, Optional
from playwright.async_api import async_playwright, Page, Browser
from mcp.server import Server
from mcp.types import Tool, TextContent
import mcp.server.stdio

# Initialize MCP server
app = Server("property-tax-scraper")

class PlaywrightScraper:
    """Handles browser automation with Playwright"""
    
    def __init__(self):
        self.playwright = None
        self.browser = None
    
    async def __aenter__(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    
    async def scrape_assessor(
        self,
        url: str,
        parcel_id: str,
        address: Optional[str] = None,
        owner_name: Optional[str] = None,
        timeout: int = 30000
    ) -> dict:
        """
        Scrape property tax data from assessor website
        
        Args:
            url: Assessor website URL
            parcel_id: Property parcel ID
            address: Property address (fallback search)
            owner_name: Owner name (fallback search)
            timeout: Page load timeout in ms
        
        Returns:
            Dict with scraped data and metadata
        """
        page = await self.browser.new_page()
        
        try:
            # Navigate to URL
            await page.goto(url, wait_until="networkidle", timeout=timeout)
            
            # Take initial screenshot
            initial_screenshot = await page.screenshot(full_page=True)
            
            # Try multiple search strategies
            search_successful = await self._try_search_strategies(
                page, parcel_id, address, owner_name
            )
            
            if not search_successful:
                return {
                    "success": False,
                    "error": "Could not find property search form or submit search",
                    "initial_url": url,
                    "initial_screenshot_base64": base64.b64encode(initial_screenshot).decode(),
                    "page_content": await page.content()[:5000]  # First 5000 chars for debugging
                }
            
            # Wait for results to load
            await page.wait_for_load_state("networkidle", timeout=timeout)
            await asyncio.sleep(2)  # Additional wait for dynamic content
            
            # Extract data
            extracted_data = await self._extract_tax_data(page)
            
            # Take final screenshot
            final_screenshot = await page.screenshot(full_page=True)
            
            return {
                "success": True,
                "data": extracted_data,
                "final_url": page.url,
                "final_screenshot_base64": base64.b64encode(final_screenshot).decode(),
                "page_title": await page.title()
            }
            
        except Exception as e:
            # Capture error state
            screenshot = None
            try:
                screenshot = await page.screenshot(full_page=True)
            except:
                pass
            
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "current_url": page.url,
                "screenshot_base64": base64.b64encode(screenshot).decode() if screenshot else None
            }
        
        finally:
            await page.close()
    
    async def _try_search_strategies(
        self,
        page: Page,
        parcel_id: str,
        address: Optional[str],
        owner_name: Optional[str]
    ) -> bool:
        """Try multiple strategies to search for property"""
        
        strategies = [
            # Strategy 1: Common parcel input patterns
            lambda: self._search_by_selector(page, [
                'input[name*="parcel" i]',
                'input[id*="parcel" i]',
                'input[placeholder*="parcel" i]',
                '#parcelId',
                '#parcel_number',
                '#ParcelNumber'
            ], parcel_id),
            
            # Strategy 2: Address search if parcel fails
            lambda: self._search_by_selector(page, [
                'input[name*="address" i]',
                'input[id*="address" i]',
                'input[placeholder*="address" i]'
            ], address) if address else False,
            
            # Strategy 3: Owner name search
            lambda: self._search_by_selector(page, [
                'input[name*="owner" i]',
                'input[id*="owner" i]',
                'input[name*="name" i]'
            ], owner_name) if owner_name else False,
            
            # Strategy 4: Generic search box
            lambda: self._search_by_selector(page, [
                'input[type="search"]',
                'input[type="text"]',
                '#search',
                '.search-input'
            ], parcel_id),
        ]
        
        for strategy in strategies:
            try:
                result = await strategy()
                if result:
                    return True
            except Exception as e:
                continue
        
        return False
    
    async def _search_by_selector(
        self,
        page: Page,
        selectors: list[str],
        value: str
    ) -> bool:
        """Try to fill and submit using list of selectors"""
        
        for selector in selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    # Fill the input
                    await element.fill(value)
                    
                    # Try to submit - multiple approaches
                    submit_success = await self._try_submit(page, element)
                    
                    if submit_success:
                        return True
            except:
                continue
        
        return False
    
    async def _try_submit(self, page: Page, input_element) -> bool:
        """Try multiple ways to submit the search"""
        
        submit_methods = [
            # Method 1: Press Enter
            lambda: input_element.press("Enter"),
            
            # Method 2: Find and click submit button
            lambda: self._click_submit_button(page),
            
            # Method 3: Submit parent form
            lambda: page.evaluate(
                "(el) => el.closest('form')?.submit()",
                input_element
            ),
        ]
        
        for method in submit_methods:
            try:
                await method()
                await asyncio.sleep(1)
                return True
            except:
                continue
        
        return False
    
    async def _click_submit_button(self, page: Page):
        """Find and click submit button"""
        button_selectors = [
            'button[type="submit"]',
            'input[type="submit"]',
            'button:has-text("Search")',
            'button:has-text("Find")',
            'button:has-text("Submit")',
            '.search-button',
            '#search-btn'
        ]
        
        for selector in button_selectors:
            try:
                button = await page.query_selector(selector)
                if button:
                    await button.click()
                    return True
            except:
                continue
        
        return False
    
    async def _extract_tax_data(self, page: Page) -> dict:
        """Extract property tax data from results page"""
        
        # Get all text content
        text_content = await page.inner_text('body')
        
        # Common data extraction patterns
        data = {
            "raw_text": text_content[:10000],  # First 10k chars
            "tables": [],
            "tax_amounts": [],
            "parcel_id": None,
            "owner": None,
            "address": None,
            "assessed_value": None,
        }
        
        # Extract tables
        tables = await page.query_selector_all('table')
        for i, table in enumerate(tables):
            table_html = await table.inner_html()
            data["tables"].append({
                "index": i,
                "html": table_html[:5000]  # Limit size
            })
        
        # Try to find specific data points with common selectors
        extraction_patterns = {
            "parcel_id": ['[class*="parcel" i]', '[id*="parcel" i]'],
            "owner": ['[class*="owner" i]', '[id*="owner" i]'],
            "address": ['[class*="address" i]', '[id*="address" i]'],
            "assessed_value": ['[class*="assessed" i]', '[class*="value" i]'],
        }
        
        for field, selectors in extraction_patterns.items():
            for selector in selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        data[field] = await element.inner_text()
                        break
                except:
                    continue
        
        return data


# Define MCP tools
@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools"""
    return [
        Tool(
            name="scrape_assessor_website",
            description=(
                "Scrape property tax data from assessor website using browser automation. "
                "Handles form submission, JavaScript rendering, and multi-page navigation. "
                "Returns extracted data, screenshots, and metadata."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Assessor website URL to scrape"
                    },
                    "parcel_id": {
                        "type": "string",
                        "description": "Property parcel ID (primary search identifier)"
                    },
                    "address": {
                        "type": "string",
                        "description": "Property address (optional, used as fallback)"
                    },
                    "owner_name": {
                        "type": "string",
                        "description": "Property owner name (optional, used as fallback)"
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Page load timeout in milliseconds (default: 30000)",
                        "default": 30000
                    }
                },
                "required": ["url", "parcel_id"]
            }
        ),
        Tool(
            name="screenshot_webpage",
            description="Take a screenshot of any webpage for verification or debugging",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL to screenshot"
                    },
                    "full_page": {
                        "type": "boolean",
                        "description": "Capture full page or just viewport",
                        "default": True
                    }
                },
                "required": ["url"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool calls"""
    
    if name == "scrape_assessor_website":
        async with PlaywrightScraper() as scraper:
            result = await scraper.scrape_assessor(
                url=arguments["url"],
                parcel_id=arguments["parcel_id"],
                address=arguments.get("address"),
                owner_name=arguments.get("owner_name"),
                timeout=arguments.get("timeout", 30000)
            )
        
        return [TextContent(
            type="text",
            text=json.dumps(result, indent=2)
        )]
    
    elif name == "screenshot_webpage":
        async with PlaywrightScraper() as scraper:
            page = await scraper.browser.new_page()
            try:
                await page.goto(arguments["url"], wait_until="networkidle")
                screenshot = await page.screenshot(
                    full_page=arguments.get("full_page", True)
                )
                result = {
                    "success": True,
                    "screenshot_base64": base64.b64encode(screenshot).decode(),
                    "url": page.url,
                    "title": await page.title()
                }
            except Exception as e:
                result = {
                    "success": False,
                    "error": str(e)
                }
            finally:
                await page.close()
        
        return [TextContent(
            type="text",
            text=json.dumps(result, indent=2)
        )]
    
    raise ValueError(f"Unknown tool: {name}")


async def main():
    """Run the MCP server"""
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())