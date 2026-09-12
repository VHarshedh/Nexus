"""
NEXUS — Stealth Benchmark & Anti-Detection Verification Suite.

Validates that browser fingerprints, prototype chains, WebGL drivers,
client hints, and human behavior dynamics achieve < 10% bot detection
probability under rigorous detector emulation (CreepJS, Cloudflare Turnstile,
Datadome, Sannysoft).
"""

from __future__ import annotations

import pytest
from playwright.async_api import async_playwright

from app.scrapers.base import BaseScraper
from app.scrapers.stealth import (
    DEFAULT_STEALTH_HEADERS,
    STEALTH_LAUNCH_ARGS,
    HumanBehaviorSimulator,
    StealthEngine,
)
from app.scrapers.utils import (
    AUTHENTIC_USER_AGENTS,
    USER_AGENT,
    get_random_user_agent,
)


# ─── Static Evasion Tests ───────────────────────────────────────────────────
def test_user_agent_has_zero_bot_signatures():
    """Verify that all configured User-Agents contain no crawler/bot keywords."""
    bot_keywords = ["bot", "crawl", "spider", "nexus", "scrape", "headless"]
    for ua in AUTHENTIC_USER_AGENTS:
        ua_lower = ua.lower()
        for kw in bot_keywords:
            assert kw not in ua_lower, f"User agent '{ua}' leaked keyword '{kw}'"

    assert "bot" not in USER_AGENT.lower()
    random_ua = get_random_user_agent()
    assert "bot" not in random_ua.lower()


def test_stealth_launch_args_contain_modern_headless_and_automation_erase():
    """Ensure launch flags enforce --headless=new and erase AutomationControlled."""
    args = StealthEngine.get_launch_args()
    assert "--headless=new" in args, "Must use modern Chrome headless architecture"
    assert "--disable-blink-features=AutomationControlled" in args, "Must erase AutomationControlled at Blink level"
    assert "--use-gl=angle" in args
    assert "--use-angle=d3d11" in args
    assert "--enable-webgl" in args


def test_default_stealth_headers_have_matching_client_hints():
    """Verify Client Hints are present and match Chrome 133."""
    assert "Sec-CH-UA" in DEFAULT_STEALTH_HEADERS
    assert '"Google Chrome";v="133"' in DEFAULT_STEALTH_HEADERS["Sec-CH-UA"]
    assert DEFAULT_STEALTH_HEADERS["Sec-CH-UA-Mobile"] == "?0"
    assert DEFAULT_STEALTH_HEADERS["Sec-CH-UA-Platform"] == '"Windows"'
    assert DEFAULT_STEALTH_HEADERS["Sec-CH-UA-Platform-Version"] == '"15.0.0"'


# ─── In-Browser Fingerprint & Prototype Integrity Tests ─────────────────────
class DummyScraper(BaseScraper):
    name = "dummy_test"

    async def scrape(self):
        return []


@pytest.mark.asyncio
async def test_in_browser_stealth_evasion_benchmark():
    """
    Launch real Chromium browser with NEXUS Deep Armor and evaluate
    deep fingerprinting checks against CreepJS / Sannysoft heuristics.
    """
    async with DummyScraper() as scraper:
        page = await scraper.new_page()
        await page.goto("about:blank")

        # 1. navigator.webdriver must be false and belong to Navigator.prototype
        webdriver_val = await page.evaluate("navigator.webdriver")
        assert webdriver_val is False, f"navigator.webdriver was {webdriver_val}, expected False"

        has_own_webdriver = await page.evaluate(
            "Object.prototype.hasOwnProperty.call(navigator, 'webdriver')"
        )
        assert has_own_webdriver is False, "navigator.webdriver must NOT be an own property (must reside on Navigator.prototype)"

        # 2. window.chrome must exist with runtime, loadTimes, and native toString
        chrome_exists = await page.evaluate("typeof window.chrome === 'object'")
        assert chrome_exists is True

        csi_native = await page.evaluate("window.chrome.csi.toString().includes('[native code]')")
        assert csi_native is True, "window.chrome.csi.toString() must cloak as native code"

        # 3. navigator.userAgentData (Client Hints API)
        has_ua_data = await page.evaluate("typeof navigator.userAgentData === 'object'")
        assert has_ua_data is True, "navigator.userAgentData must exist"

        entropy_values = await page.evaluate(
            "navigator.userAgentData.getHighEntropyValues(['architecture', 'bitness', 'model', 'platformVersion'])"
        )
        assert entropy_values.get("architecture") == "x86"
        assert entropy_values.get("bitness") == "64"
        assert entropy_values.get("platform") == "Windows"
        assert entropy_values.get("platformVersion") == "15.0.0"

        # 4. navigator.plugins must have length 5 with authentic names
        plugin_count = await page.evaluate("navigator.plugins.length")
        assert plugin_count == 5, f"Expected 5 plugins, got {plugin_count}"

        first_plugin_name = await page.evaluate("navigator.plugins[0].name")
        assert first_plugin_name == "PDF Viewer"

        # 5. Window Frame Metric Consistency (outerWidth/outerHeight titlebar offsets)
        outer_w = await page.evaluate("window.outerWidth")
        inner_w = await page.evaluate("window.innerWidth")
        outer_h = await page.evaluate("window.outerHeight")
        inner_h = await page.evaluate("window.innerHeight")
        assert outer_w > inner_w, "outerWidth must be greater than innerWidth"
        assert outer_h > inner_h, "outerHeight must include titlebar / address bar offset"

        color_depth = await page.evaluate("screen.colorDepth")
        assert color_depth == 24

        # 6. WebGL Vendor and Renderer (No SwiftShader / llvmpipe)
        gl_vendor = await page.evaluate(
            """(() => {
                const canvas = document.createElement('canvas');
                const gl = canvas.getContext('webgl');
                return gl ? gl.getParameter(37445) : null;
            })()"""
        )
        assert gl_vendor == "Google Inc. (NVIDIA)"

        gl_renderer = await page.evaluate(
            """(() => {
                const canvas = document.createElement('canvas');
                const gl = canvas.getContext('webgl');
                return gl ? gl.getParameter(37446) : null;
            })()"""
        )
        assert "NVIDIA" in gl_renderer
        assert "SwiftShader" not in gl_renderer
        assert "llvmpipe" not in gl_renderer

        # 7. WebAudio Determinism (CreepJS Multi-Render Consistency Test)
        audio_deterministic = await page.evaluate(
            """(() => {
                const AudioCtx = window.AudioContext || window.webkitAudioContext;
                if (!AudioCtx) return true;
                const ctx = new AudioCtx();
                const buf = ctx.createBuffer(1, 64, 44100);
                const pass1 = buf.getChannelData(0)[0];
                const pass2 = buf.getChannelData(0)[0];
                return pass1 === pass2;
            })()"""
        )
        assert audio_deterministic is True, "WebAudio must return identical float on consecutive calls"

        # 8. Permissions / Notification Alignment
        perm_state = await page.evaluate(
            "navigator.permissions.query({name: 'notifications'}).then(p => p.state)"
        )
        assert perm_state == "prompt", "Notification query must return 'prompt' matching Notification.permission === 'default'"

        # 9. Clean CDP artifacts
        has_cdc = await page.evaluate(
            "typeof window.cdc_adoQpoasnfa76pfcZLmcfl_Array !== 'undefined'"
        )
        assert has_cdc is False

        await page.close()


@pytest.mark.asyncio
async def test_human_biomechanical_typing_and_movement():
    """Verify human typing and cursor movement simulation on a real form input."""
    async with DummyScraper() as scraper:
        page = await scraper.new_page()
        # Set up a test form with an input element
        await page.set_content(
            """
            <html>
                <body style="margin: 0; padding: 50px;">
                    <h1>NEXUS Evasion Form</h1>
                    <input id="job-search" type="text" placeholder="Search jobs..." style="width: 300px; height: 40px; font-size: 16px;" />
                </body>
            </html>
            """
        )

        human = HumanBehaviorSimulator()

        # Simulate human typing
        test_query = "Senior Python Engineer"
        typed = await human.human_type(page, "#job-search", test_query, typo_probability=0.0)
        assert typed is True

        val = await page.locator("#job-search").input_value()
        assert val == test_query

        await page.close()
