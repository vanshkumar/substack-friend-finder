"""Browser-based Substack client using Playwright to bypass Cloudflare."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

from .cache import cache
from .types import Newsletter, UserProfile

# Browser instance (reused across calls)
_browser: Optional[Browser] = None
_context: Optional[BrowserContext] = None
_page: Optional[Page] = None

# Rate limiting
MIN_REQUEST_INTERVAL = 1.5  # seconds between requests
_last_request_time = 0.0


def _rate_limit() -> None:
    """Ensure we don't exceed rate limits."""
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < MIN_REQUEST_INTERVAL:
        time.sleep(MIN_REQUEST_INTERVAL - elapsed)
    _last_request_time = time.time()


def init_browser(cookies_file: Optional[str] = None) -> bool:
    """
    Initialize the browser with Substack session cookies.

    Args:
        cookies_file: Path to cookies JSON file. If None, looks for ~/.substack-cookies.json

    Returns:
        True if browser initialized successfully
    """
    global _browser, _context, _page

    # Find cookies file
    if cookies_file:
        cookie_path = Path(cookies_file)
    else:
        cookie_path = Path.home() / ".substack-cookies.json"

    if not cookie_path.exists():
        print(f"Cookies file not found: {cookie_path}")
        return False

    try:
        with open(cookie_path) as f:
            cookies_data = json.load(f)
    except Exception as e:
        print(f"Error reading cookies: {e}")
        return False

    # Start browser (non-headless to handle Cloudflare better)
    playwright = sync_playwright().start()
    _browser = playwright.chromium.launch(
        headless=False,  # Cloudflare detects headless browsers
        args=['--disable-blink-features=AutomationControlled']
    )
    _context = _browser.new_context(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:146.0) Gecko/20100101 Firefox/146.0",
        viewport={"width": 1280, "height": 720},
    )

    # Convert cookies to Playwright format
    playwright_cookies = []
    for name, value in cookies_data.items():
        playwright_cookies.append({
            "name": name,
            "value": value,
            "domain": ".substack.com",
            "path": "/",
        })

    _context.add_cookies(playwright_cookies)
    _page = _context.new_page()

    # Navigate to Substack homepage first
    print("Navigating to Substack...")
    _page.goto("https://substack.com", wait_until="load", timeout=60000)
    time.sleep(2)  # Let page settle

    # Check if we hit a Cloudflare challenge
    if "Just a moment" in _page.content():
        print("Waiting for Cloudflare challenge...")
        time.sleep(10)  # Wait for Cloudflare to resolve

    return True


def close_browser() -> None:
    """Close the browser."""
    global _browser, _context, _page
    if _page:
        _page.close()
    if _context:
        _context.close()
    if _browser:
        _browser.close()
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


def get_publication_subscribers_browser(user_id: int, username: str = "", limit: int = 100) -> List[UserProfile]:
    """
    Get subscribers of a publication using the browser's authenticated fetch.

    Args:
        user_id: The numeric user ID of the publication owner
        username: The username/handle (not used, kept for compatibility)
        limit: Maximum number of subscribers to fetch

    Returns:
        List of UserProfile objects for subscribers
    """
    cache_key = f"subscribers_browser:{user_id}:{limit}"
    cached = cache.get(cache_key)
    if cached:
        return [UserProfile(**p) for p in cached]

    url = f"https://substack.com/api/v1/user/{user_id}/subscriber-lists"
    print(f"  Fetching subscribers for user_id={user_id}...")
    data = _fetch_api(url, {"lists": "subscribers"})

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
