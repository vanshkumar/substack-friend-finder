"""Browser-based Substack client using Playwright to bypass Cloudflare."""

from __future__ import annotations

import glob
import json
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page, Playwright
from playwright_stealth import stealth_sync

# Try to import undetected_chromedriver for Cloudflare bypass
try:
    import undetected_chromedriver as uc
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    HAS_UNDETECTED_CHROME = True
except ImportError:
    HAS_UNDETECTED_CHROME = False

from .cache import cache
from .types import Newsletter, UserProfile

# Browser instance (reused across calls)
_playwright: Optional[Playwright] = None
_browser: Optional[Browser] = None
_context: Optional[BrowserContext] = None
_page: Optional[Page] = None

# Undetected Chrome driver (for Cloudflare-protected endpoints)
_chrome_driver = None

# Rate limiting - use random delays to appear more human
import random
MIN_REQUEST_INTERVAL = 8.0  # minimum seconds between requests
MAX_REQUEST_INTERVAL = 15.0  # maximum seconds between requests
_last_request_time = 0.0


def _rate_limit() -> None:
    """Ensure we don't exceed rate limits with random human-like delays."""
    global _last_request_time
    delay = random.uniform(MIN_REQUEST_INTERVAL, MAX_REQUEST_INTERVAL)
    elapsed = time.time() - _last_request_time
    if elapsed < delay:
        time.sleep(delay - elapsed)
    _last_request_time = time.time()


def _new_stealth_page() -> Page:
    """Create a new page with stealth mode enabled to bypass bot detection."""
    global _context
    if not _context:
        raise RuntimeError("Browser not initialized")
    page = _context.new_page()
    # Temporarily disabled stealth to debug response capture issue
    # stealth_sync(page)
    return page


def _get_browser_cookies() -> List[Dict]:
    """Get Substack cookies from user's browser (Firefox, Chrome, Safari)."""
    try:
        import browser_cookie3
    except ImportError:
        print("browser_cookie3 not installed. Run: pip install browser_cookie3")
        return []

    cookies = []

    # Try browsers in order: Firefox, Chrome, Safari
    browsers = [
        ("Firefox", browser_cookie3.firefox),
        ("Chrome", browser_cookie3.chrome),
        ("Safari", browser_cookie3.safari),
    ]

    for name, browser_fn in browsers:
        try:
            cj = browser_fn(domain_name=".substack.com")
            for c in cj:
                cookies.append({
                    "name": c.name,
                    "value": c.value,
                    "domain": ".substack.com",
                    "path": c.path or "/",
                })
            if cookies:
                print(f"Loaded {len(cookies)} cookies from {name}")
                return cookies
        except Exception as e:
            # Silently try next browser
            pass

    return cookies


def _find_firefox_profile() -> Optional[str]:
    """Find the user's Firefox profile directory."""
    # macOS path
    mac_path = os.path.expanduser("~/Library/Application Support/Firefox/Profiles")
    # Linux path
    linux_path = os.path.expanduser("~/.mozilla/firefox")

    profile_dir = mac_path if os.path.exists(mac_path) else linux_path

    if not os.path.exists(profile_dir):
        return None

    # Find the default-release profile (most recently used)
    profiles = glob.glob(os.path.join(profile_dir, "*.default-release*"))
    if not profiles:
        profiles = glob.glob(os.path.join(profile_dir, "*.default*"))

    if profiles:
        # Return the most recently modified one
        profiles.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        return profiles[0]

    return None


def init_browser(cookies_file: Optional[str] = None) -> bool:
    """
    Initialize the browser with cookies from user's existing browser session.

    Automatically pulls cookies from Firefox/Chrome/Safari.

    Returns:
        True if browser initialized successfully
    """
    global _playwright, _browser, _context, _page

    _playwright = sync_playwright().start()

    # Try to use Firefox profile directly for better Cloudflare compatibility
    firefox_profile = _find_firefox_profile()
    if firefox_profile:
        print(f"Using Firefox profile: {firefox_profile}")
        try:
            # Copy profile to avoid conflicts with running Firefox
            temp_profile = tempfile.mkdtemp(prefix="substack_firefox_")
            print(f"Copying profile to temp location...")

            # Only copy essential files for session state
            essential_files = [
                "cookies.sqlite",
                "permissions.sqlite",
                "prefs.js",
                "storage",
            ]
            for item in essential_files:
                src = os.path.join(firefox_profile, item)
                dst = os.path.join(temp_profile, item)
                if os.path.exists(src):
                    if os.path.isdir(src):
                        shutil.copytree(src, dst, dirs_exist_ok=True)
                    else:
                        shutil.copy2(src, dst)

            _context = _playwright.firefox.launch_persistent_context(
                temp_profile,
                headless=False,
                viewport={"width": 1280, "height": 720},
            )
            print("Browser initialized with Firefox profile.")
            return True
        except Exception as e:
            print(f"Could not use Firefox profile: {e}")
            print("Falling back to cookie-based approach...")

    # Fallback: Get cookies from user's browser
    cookies = _get_browser_cookies()
    if not cookies:
        print("Could not get cookies from any browser.")
        print("Make sure you're logged into Substack in Firefox, Chrome, or Safari.")
        return False

    # Verify we have session cookie
    has_session = any(c["name"] == "substack.sid" for c in cookies)
    if not has_session:
        print("Warning: No session cookie found. Please log into Substack in your browser and try again.")
        return False

    # Start browser (Firefox works better with Cloudflare than Chromium)
    _browser = _playwright.firefox.launch(headless=False)
    _context = _browser.new_context(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:146.0) Gecko/20100101 Firefox/146.0",
        viewport={"width": 1280, "height": 720},
    )

    # Add cookies from user's browser
    _context.add_cookies(cookies)

    # Don't navigate to substack.com - it breaks subsequent subdomain navigation
    # The cookies already have Cloudflare clearance from Firefox
    print("Browser initialized with session cookies.")
    return True


def close_browser() -> None:
    """Close the browser."""
    global _playwright, _browser, _context, _page, _chrome_driver
    if _page:
        _page.close()
    if _context:
        _context.close()
    if _browser:
        _browser.close()
    if _playwright:
        _playwright.stop()
    if _chrome_driver:
        _chrome_driver.quit()
    _playwright = None
    _browser = None
    _context = None
    _page = None
    _chrome_driver = None


def _init_undetected_chrome() -> bool:
    """Initialize undetected Chrome driver for Cloudflare bypass."""
    global _chrome_driver

    if not HAS_UNDETECTED_CHROME:
        print("undetected_chromedriver not installed")
        return False

    if _chrome_driver:
        return True

    try:
        # Workaround for SSL certificate issues on macOS
        import ssl
        ssl._create_default_https_context = ssl._create_unverified_context

        print("Initializing undetected Chrome driver...")
        options = uc.ChromeOptions()
        options.add_argument("--window-size=1280,720")

        # Get cookies from Chrome to add to the session
        cookies = _get_browser_cookies()

        _chrome_driver = uc.Chrome(options=options)

        # Navigate to substack and add cookies
        _chrome_driver.get("https://substack.com")
        time.sleep(2)

        # Add substack cookies
        for cookie in cookies:
            try:
                _chrome_driver.add_cookie({
                    "name": cookie["name"],
                    "value": cookie["value"],
                    "domain": cookie.get("domain", ".substack.com"),
                    "path": cookie.get("path", "/"),
                })
            except:
                pass

        # Refresh to apply cookies
        _chrome_driver.refresh()
        time.sleep(2)

        print("Undetected Chrome driver initialized.")
        return True
    except Exception as e:
        print(f"Failed to initialize undetected Chrome: {e}")
        return False


def _fetch_subscriber_lists_chrome(author_handle: str, list_type: str = "subscribers") -> Optional[Dict]:
    """
    Fetch subscriber-lists using undetected Chrome driver.

    Args:
        author_handle: The author's handle
        list_type: "subscribers" or "followers"

    Returns:
        API response data or None
    """
    global _chrome_driver

    if not _chrome_driver and not _init_undetected_chrome():
        return None

    _rate_limit()

    try:
        # First, get the user ID from the profile
        profile_url = f"https://substack.com/@{author_handle}"
        _chrome_driver.get(profile_url)

        # Wait for page to load
        time.sleep(random.uniform(3, 5))

        # Check for Cloudflare challenge
        if "Just a moment" in _chrome_driver.page_source:
            time.sleep(10)

        # Get user ID from the profile API
        profile_api_url = f"https://substack.com/api/v1/user/{author_handle}/public_profile"
        profile_result = _chrome_driver.execute_async_script(f"""
            var callback = arguments[arguments.length - 1];
            fetch("{profile_api_url}", {{
                credentials: 'include',
                headers: {{'Accept': 'application/json'}}
            }})
            .then(r => r.json())
            .then(data => callback(data))
            .catch(e => callback({{error: e.toString()}}));
        """)

        if not profile_result or "error" in profile_result:
            return None

        user_id = profile_result.get("id")
        if not user_id:
            return None

        # Navigate to the subscribers/followers page
        url = f"https://substack.com/@{author_handle}/{list_type}"
        _chrome_driver.get(url)
        time.sleep(random.uniform(2, 4))

        # Execute JavaScript to fetch the API data directly using user ID
        api_url = f"https://substack.com/api/v1/user/{user_id}/subscriber-lists?lists={list_type}"

        # Use async/await properly in the execute_script
        result = _chrome_driver.execute_async_script(f"""
            var callback = arguments[arguments.length - 1];
            fetch("{api_url}", {{
                credentials: 'include',
                headers: {{'Accept': 'application/json'}}
            }})
            .then(r => {{
                console.log('Status:', r.status);
                if (!r.ok) {{
                    return r.text().then(text => ({{error: r.status, body: text.substring(0, 200)}}));
                }}
                return r.json();
            }})
            .then(data => callback(data))
            .catch(e => callback({{error: e.toString()}}));
        """)

        if isinstance(result, dict) and "error" in result:
            return None

        return result
    except Exception as e:
        return None


def _fetch_api(url: str, params: Optional[Dict[str, str]] = None) -> Optional[Dict]:
    """Fetch from Substack API using the browser."""
    global _page

    if not _page:
        print("Browser not initialized. Call init_browser() first.")
        return None

    _rate_limit()

    # Build full URL with params
    if params:
        param_str = "&".join(f"{k}={v}" for k, v in params.items())
        full_url = f"{url}?{param_str}"
    else:
        full_url = url

    try:
        # Use page.evaluate to make fetch request with browser's cookies
        result = _page.evaluate(f"""
            async () => {{
                const response = await fetch("{full_url}", {{
                    credentials: 'include',
                    headers: {{
                        'Accept': 'application/json',
                    }}
                }});
                if (!response.ok) {{
                    return {{ error: response.status, message: await response.text() }};
                }}
                return await response.json();
            }}
        """)

        if isinstance(result, dict) and "error" in result:
            print(f"API error {result['error']}: {result.get('message', '')[:100]}")
            return None

        return result
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None


def get_user_subscriptions_browser(username: str) -> List[Newsletter]:
    """Get a user's subscriptions using the browser."""
    cache_key = f"subscriptions:{username}"
    cached = cache.get(cache_key)
    if cached:
        return [Newsletter(**n) for n in cached]

    url = f"https://substack.com/api/v1/user/{username}/public_profile"
    data = _fetch_api(url)

    if not data:
        return []

    subs_data = data.get("subscriptions", [])
    newsletters = []

    for sub in subs_data:
        pub = sub.get("publication", {})
        if not pub:
            continue

        author = pub.get("author", {})
        author_id = pub.get("author_id") or pub.get("primary_user_id") or author.get("id", 0)

        newsletter = Newsletter(
            id=pub.get("id", 0),
            name=pub.get("name", "Unknown"),
            subdomain=pub.get("subdomain", ""),
            author_id=author_id,
            subscriber_count=pub.get("subscriber_count", 0),
            url=f"https://{pub.get('subdomain', '')}.substack.com" if pub.get("subdomain") else None,
        )
        newsletters.append(newsletter)

    # Cache results
    cache.set(cache_key, [
        {
            "id": n.id,
            "name": n.name,
            "subdomain": n.subdomain,
            "author_id": n.author_id,
            "subscriber_count": n.subscriber_count,
            "url": n.url,
        }
        for n in newsletters
    ])

    return newsletters


def _get_author_handle(subdomain: str) -> Optional[str]:
    """Get the author's handle from a publication subdomain."""
    global _context

    if not _context:
        return None

    _rate_limit()

    # Use a fresh page to avoid React routing issues
    page = _new_stealth_page()

    try:
        # Navigate directly to publication (don't reuse main page)
        page.goto(f"https://{subdomain}.substack.com", wait_until="load", timeout=30000)

        # Handle Cloudflare if needed
        for _ in range(6):
            if "Just a moment" in page.content():
                time.sleep(5)
            else:
                break

        time.sleep(1)

        # Look for author link in the page content
        content = page.content()
        import re

        # Try multiple patterns
        patterns = [
            r'substack\.com/@([a-zA-Z0-9_-]+)',  # Full URL pattern
            r'href="/@([^"/?]+)"',               # Relative link pattern
            r'"handle":"([^"]+)"',               # JSON data pattern
        ]

        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                return match.group(1)
    except Exception as e:
        print(f"  Error getting author handle: {e}")
    finally:
        page.close()

    return None


def get_publication_subscribers_browser(author_handle: str, limit: int = 100) -> List[UserProfile]:
    """
    Get subscribers of a publication by navigating to the subscribers page.

    Args:
        author_handle: The author's handle (e.g., 'andrewjrose')
        limit: Maximum number of subscribers to fetch

    Returns:
        List of UserProfile objects for subscribers
    """
    global _context

    if not _context:
        print("Browser not initialized")
        return []

    cache_key = f"subscribers_browser:{author_handle}:{limit}"
    cached = cache.get(cache_key)
    if cached:
        return [UserProfile(**p) for p in cached]

    _rate_limit()

    # Use fresh page to avoid React routing issues
    page = _new_stealth_page()

    # Capture API response via interception
    captured_data: List[Dict] = []

    def handle_response(response):
        if "subscriber-lists" in response.url and "substack.com/api" in response.url:
            try:
                if response.status == 200:
                    captured_data.append(response.json())
            except:
                pass

    page.on("response", handle_response)

    try:
        # Navigate to profile first (more human-like)
        profile_url = f"https://substack.com/@{author_handle}"
        page.goto(profile_url, wait_until="networkidle", timeout=60000)
        time.sleep(random.uniform(1, 2))  # Human-like pause

        # Click on Subscribers link
        try:
            subs_link = page.locator("text=Subscribers").first
            if subs_link.is_visible():
                subs_link.click()
                page.wait_for_load_state("networkidle", timeout=30000)
                time.sleep(2)
            else:
                page.goto(f"{profile_url}/subscribers", wait_until="networkidle", timeout=60000)
        except:
            page.goto(f"{profile_url}/subscribers", wait_until="networkidle", timeout=60000)

        # Wait for Cloudflare if needed
        for _ in range(6):
            if "Just a moment" in page.content():
                time.sleep(5)
            else:
                break

        time.sleep(2)  # Wait for API response

    except Exception as e:
        print(f"  Navigation error: {e}")

    page.remove_listener("response", handle_response)
    page.close()

    if not captured_data:
        # Try undetected Chrome as fallback (works better with Cloudflare)
        if HAS_UNDETECTED_CHROME:
            data = _fetch_subscriber_lists_chrome(author_handle, "subscribers")
            if data:
                captured_data = [data]

    if not captured_data:
        return []

    data = captured_data[0]

    if not data:
        print("  Could not fetch subscriber data")
        return []

    # Response structure: { subscriberLists: [{ groups: [{ users: [...] }] }] }
    subscribers = []
    all_users = []

    subscriber_lists = data.get("subscriberLists", [])
    for sub_list in subscriber_lists:
        groups = sub_list.get("groups", [])
        for group in groups:
            users = group.get("users", [])
            all_users.extend(users)

    print(f"  Got {len(all_users)} total subscribers")
    subscriber_list = all_users[:limit]

    for s in subscriber_list:
        profile = UserProfile(
            id=s.get("id", 0),
            username=s.get("handle", s.get("username", "")),
            name=s.get("name", ""),
            bio=s.get("bio"),
            photo_url=s.get("photo_url"),
            has_publication=bool(s.get("primaryPublication")),
            publication_url=s.get("primaryPublication", {}).get("url") if s.get("primaryPublication") else None,
            follower_count=s.get("followerCount", 0),
        )
        subscribers.append(profile)

    # Cache results
    cache.set(cache_key, [
        {
            "id": p.id,
            "username": p.username,
            "name": p.name,
            "bio": p.bio,
            "photo_url": p.photo_url,
            "has_publication": p.has_publication,
            "publication_url": p.publication_url,
            "follower_count": p.follower_count,
        }
        for p in subscribers
    ])

    return subscribers


def get_publication_followers_browser(author_handle: str, limit: int = 100) -> List[UserProfile]:
    """
    Get followers of a publication by navigating to the followers page.

    Args:
        author_handle: The author's handle (e.g., 'andrewjrose')
        limit: Maximum number of followers to fetch

    Returns:
        List of UserProfile objects for followers
    """
    global _context

    if not _context:
        print("Browser not initialized")
        return []

    cache_key = f"followers_browser:{author_handle}:{limit}"
    cached = cache.get(cache_key)
    if cached:
        return [UserProfile(**p) for p in cached]

    _rate_limit()

    # Use fresh page to avoid React routing issues
    page = _new_stealth_page()

    # Capture API response via interception
    captured_data: List[Dict] = []

    def handle_response(response):
        if "subscriber-lists" in response.url and "substack.com/api" in response.url:
            try:
                if response.status == 200:
                    captured_data.append(response.json())
            except:
                pass

    page.on("response", handle_response)

    page_url = f"https://substack.com/@{author_handle}/followers"

    try:
        page.goto(page_url, wait_until="networkidle", timeout=60000)

        # Wait for Cloudflare if needed
        for _ in range(6):
            if "Just a moment" in page.content():
                time.sleep(5)
            else:
                break

        time.sleep(2)  # Wait for API response

    except:
        pass

    page.remove_listener("response", handle_response)
    page.close()

    if not captured_data:
        # Try undetected Chrome as fallback (works better with Cloudflare)
        if HAS_UNDETECTED_CHROME:
            data = _fetch_subscriber_lists_chrome(author_handle, "followers")
            if data:
                captured_data = [data]

    if not captured_data:
        return []

    data = captured_data[0]

    if not data:
        return []

    # Response structure: { subscriberLists: [{ groups: [{ users: [...] }] }] }
    followers = []
    all_users = []

    subscriber_lists = data.get("subscriberLists", [])
    for sub_list in subscriber_lists:
        groups = sub_list.get("groups", [])
        for group in groups:
            users = group.get("users", [])
            all_users.extend(users)

    print(f"  Got {len(all_users)} total followers")
    follower_list = all_users[:limit]

    for f in follower_list:
        profile = UserProfile(
            id=f.get("id", 0),
            username=f.get("handle", f.get("username", "")),
            name=f.get("name", ""),
            bio=f.get("bio"),
            photo_url=f.get("photo_url"),
            has_publication=bool(f.get("primaryPublication")),
            publication_url=f.get("primaryPublication", {}).get("url") if f.get("primaryPublication") else None,
            follower_count=f.get("followerCount", 0),
        )
        followers.append(profile)

    # Cache results
    cache.set(cache_key, [
        {
            "id": p.id,
            "username": p.username,
            "name": p.name,
            "bio": p.bio,
            "photo_url": p.photo_url,
            "has_publication": p.has_publication,
            "publication_url": p.publication_url,
            "follower_count": p.follower_count,
        }
        for p in followers
    ])

    return followers
