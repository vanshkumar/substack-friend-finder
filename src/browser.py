"""Browser-based Substack client using Playwright to bypass Cloudflare."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page, Playwright

from .cache import cache
from .types import Newsletter, UserProfile

# Browser instance (reused across calls)
_playwright: Optional[Playwright] = None
_browser: Optional[Browser] = None
_context: Optional[BrowserContext] = None
_page: Optional[Page] = None

# Rate limiting
MIN_REQUEST_INTERVAL = 3.0  # seconds between requests
_last_request_time = 0.0


def _rate_limit() -> None:
    """Ensure we don't exceed rate limits."""
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < MIN_REQUEST_INTERVAL:
        time.sleep(MIN_REQUEST_INTERVAL - elapsed)
    _last_request_time = time.time()


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


def init_browser(cookies_file: Optional[str] = None) -> bool:
    """
    Initialize the browser with cookies from user's existing browser session.

    Automatically pulls cookies from Firefox/Chrome/Safari.

    Returns:
        True if browser initialized successfully
    """
    global _playwright, _browser, _context, _page

    # Get cookies from user's browser
    cookies = _get_browser_cookies()
    if not cookies:
        print("Could not get cookies from any browser.")
        print("Make sure you're logged into Substack in Firefox, Chrome, or Safari.")
        return False

    # Start browser
    _playwright = sync_playwright().start()
    _browser = _playwright.chromium.launch(
        headless=False,  # Cloudflare detects headless browsers
        args=['--disable-blink-features=AutomationControlled']
    )
    _context = _browser.new_context(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:146.0) Gecko/20100101 Firefox/146.0",
        viewport={"width": 1280, "height": 720},
    )

    # Add cookies from user's browser
    _context.add_cookies(cookies)
    _page = _context.new_page()

    # Navigate to Substack homepage
    print("Navigating to Substack...")
    _page.goto("https://substack.com", wait_until="load", timeout=60000)

    # Wait for Cloudflare challenge to resolve
    for i in range(12):  # Up to 60 seconds
        if "Just a moment" in _page.content():
            print(f"Waiting for Cloudflare... ({i+1})")
            time.sleep(5)
        else:
            break

    time.sleep(2)  # Let page settle

    # Verify we're logged in
    _page.goto("https://substack.com/home", wait_until="load", timeout=60000)
    time.sleep(2)

    if "Sign in" in _page.content() and _page.locator('a[href="/sign-in"]').count() > 0:
        print("Warning: Cookies may be expired. Please log into Substack in your browser and try again.")
        return False

    print("Logged in to Substack.")
    return True


def close_browser() -> None:
    """Close the browser."""
    global _playwright, _browser, _context, _page
    if _page:
        _page.close()
    if _context:
        _context.close()
    if _browser:
        _browser.close()
    if _playwright:
        _playwright.stop()
    _playwright = None
    _browser = None
    _context = None
    _page = None


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
    global _page

    if not _page:
        return None

    try:
        # Navigate to publication and extract author handle from page
        _page.goto(f"https://{subdomain}.substack.com", wait_until="load", timeout=30000)
        time.sleep(1)

        # Look for author link in the page content
        content = _page.content()
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

    return None


def get_publication_subscribers_browser(user_id: int, subdomain: str = "", limit: int = 100) -> List[UserProfile]:
    """
    Get subscribers of a publication by navigating to the subscribers page.

    Args:
        user_id: The numeric user ID of the publication owner
        subdomain: The publication subdomain (used to find author handle)
        limit: Maximum number of subscribers to fetch

    Returns:
        List of UserProfile objects for subscribers
    """
    global _page

    if not _page:
        print("Browser not initialized")
        return []

    cache_key = f"subscribers_browser:{user_id}:{limit}"
    cached = cache.get(cache_key)
    if cached:
        return [UserProfile(**p) for p in cached]

    _rate_limit()

    # Get author handle from subdomain
    author_handle = None
    if subdomain:
        author_handle = _get_author_handle(subdomain)

    if not author_handle:
        print("  Could not find author handle")
        return []

    # Capture API response via interception
    captured_data: List[Dict] = []

    def handle_response(response):
        if "subscriber-lists" in response.url and "substack.com/api" in response.url:
            try:
                if response.status == 200:
                    captured_data.append(response.json())
            except:
                pass

    _page.on("response", handle_response)

    page_url = f"https://substack.com/@{author_handle}/subscribers"
    print(f"  Fetching subscribers from @{author_handle}...")

    try:
        _page.goto(page_url, wait_until="networkidle", timeout=60000)

        # Wait for Cloudflare if needed
        for _ in range(6):
            if "Just a moment" in _page.content():
                time.sleep(5)
            else:
                break

        time.sleep(2)  # Wait for API response

    except Exception as e:
        print(f"  Navigation error: {e}")

    _page.remove_listener("response", handle_response)

    if not captured_data:
        print("  Could not fetch subscriber data")
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


def get_publication_followers_browser(user_id: int, limit: int = 100) -> List[UserProfile]:
    """
    Get followers of a publication using the browser.

    Args:
        user_id: The numeric user ID of the publication owner
        limit: Maximum number of followers to fetch

    Returns:
        List of UserProfile objects for followers
    """
    cache_key = f"followers_browser:{user_id}:{limit}"
    cached = cache.get(cache_key)
    if cached:
        return [UserProfile(**p) for p in cached]

    url = f"https://substack.com/api/v1/user/{user_id}/subscriber-lists"
    data = _fetch_api(url, {"lists": "followers"})

    if not data:
        return []

    followers = []
    follower_list = data.get("followers", [])[:limit]

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
