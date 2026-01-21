#!/usr/bin/env python3
"""
Automated test script for the Substack Friend Finder extension.

Uses Playwright to:
1. Launch Chrome with user's existing profile (for cookies)
2. Load the extension
3. Test API endpoints and extension functionality
4. Report what works and what doesn't

Usage:
    python extension/test_extension.py [username]

If username is not provided, it will use a default test user.
"""

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from playwright.sync_api import sync_playwright, Page


def get_chrome_user_data_dir():
    """Get Chrome's default user data directory."""
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/Google/Chrome")
    elif sys.platform == "win32":
        return os.path.expanduser("~\\AppData\\Local\\Google\\Chrome\\User Data")
    else:
        return os.path.expanduser("~/.config/google-chrome")


def rate_limit_delay():
    """Add a random delay to avoid rate limiting."""
    delay = random.uniform(2, 4)
    print(f"    (waiting {delay:.1f}s)")
    time.sleep(delay)


def test_api_endpoint(page: Page, url: str, name: str, retries: int = 2) -> dict:
    """Test an API endpoint and return results."""
    print(f"  Testing: {name}")
    print(f"    URL: {url}")

    for attempt in range(retries):
        if attempt > 0:
            wait_time = 5 * (attempt + 1)
            print(f"    Retry {attempt + 1}/{retries} after {wait_time}s...")
            time.sleep(wait_time)

        try:
            result = page.evaluate(f"""
                async () => {{
                    try {{
                        const response = await fetch("{url}", {{
                            credentials: 'include',
                            headers: {{ 'Accept': 'application/json' }}
                        }});
                        const status = response.status;
                        const statusText = response.statusText;
                        let data = null;
                        let error = null;

                        if (response.ok) {{
                            data = await response.json();
                        }} else {{
                            error = await response.text();
                        }}

                        return {{ status, statusText, data, error: error ? error.substring(0, 500) : null }};
                    }} catch (e) {{
                        return {{ status: 0, error: e.toString() }};
                    }}
                }}
            """)

            if result["status"] == 200:
                print(f"    ✓ Status: {result['status']} OK")
                return {"success": True, "data": result["data"]}
            elif result["status"] == 429:
                print(f"    ⚠ Rate limited (429)")
                if attempt < retries - 1:
                    continue
                return {"success": False, "status": 429, "error": "Rate limited"}
            else:
                print(f"    ✗ Status: {result['status']} {result.get('statusText', '')}")
                if result.get("error"):
                    if "cloudflare" in result["error"].lower():
                        print(f"    ⚠ Cloudflare challenge detected")
                    else:
                        print(f"    Error: {result['error'][:200]}")
                return {"success": False, "status": result["status"], "error": result.get("error")}

        except Exception as e:
            print(f"    ✗ Exception: {e}")
            return {"success": False, "error": str(e)}

    return {"success": False, "error": "Max retries exceeded"}


def test_from_subscribers_page(page: Page, author_handle: str, author_id: int) -> dict:
    """Navigate to subscribers page and test API from there."""
    print(f"\n  Navigating to @{author_handle}/subscribers...")

    try:
        page.goto(f"https://substack.com/@{author_handle}/subscribers", wait_until="networkidle", timeout=60000)
        time.sleep(5)

        # Check for Cloudflare challenge
        content = page.content()
        title = page.title()
        print(f"    Page title: {title}")

        if "Just a moment" in content or "Cloudflare" in content:
            print("    ⚠ Cloudflare challenge - waiting 15s...")
            time.sleep(15)
            content = page.content()
            title = page.title()
            print(f"    Page title after wait: {title}")

        print(f"    Current URL: {page.url}")

        # Check if we can see subscriber content
        has_subscribers = "subscriber" in content.lower() and "list" in content.lower()
        print(f"    Has subscriber content: {has_subscribers}")

        # Now test the API from this page context
        rate_limit_delay()
        url = f"https://substack.com/api/v1/user/{author_id}/subscriber-lists?lists=subscribers"
        return test_api_endpoint(page, url, "subscriber-lists from subscribers page")

    except Exception as e:
        print(f"    ✗ Navigation failed: {e}")
        return {"success": False, "error": str(e)}


def run_tests(username: str = None, skip_extension: bool = False):
    """Run all tests."""
    extension_path = Path(__file__).parent.absolute()

    print("=" * 60)
    print("Substack Friend Finder - Extension Test")
    print("=" * 60)
    print(f"\nExtension path: {extension_path}")

    with sync_playwright() as p:
        print("\nLaunching Chrome...")

        user_data_dir = get_chrome_user_data_dir()
        print(f"Chrome user data: {user_data_dir}")

        import tempfile
        import shutil

        temp_profile = tempfile.mkdtemp(prefix="sff_test_")
        print(f"Temp profile: {temp_profile}")

        try:
            # Check for SID cookie in environment or argument
            sid_cookie = os.environ.get("SUBSTACK_SID")

            # Build launch args
            args = [
                "--no-first-run",
                "--no-default-browser-check",
            ]

            if not skip_extension:
                args.extend([
                    f"--disable-extensions-except={extension_path}",
                    f"--load-extension={extension_path}",
                ])

            context = p.chromium.launch_persistent_context(
                temp_profile,
                headless=False,
                channel="chrome",  # Use installed Chrome, not Chromium
                args=args,
                ignore_default_args=["--enable-automation"],
            )

            page = context.new_page()

            # Add SID cookie if provided
            if sid_cookie:
                print(f"  Adding substack.sid cookie...")
                context.add_cookies([{
                    "name": "substack.sid",
                    "value": sid_cookie,
                    "domain": ".substack.com",
                    "path": "/"
                }])

            # Navigate to Substack
            print("\nNavigating to substack.com...")
            page.goto("https://substack.com", wait_until="networkidle", timeout=30000)
            time.sleep(2)

            # Check cookies
            cookies = context.cookies()
            substack_cookies = [c for c in cookies if "substack" in c.get("domain", "")]
            print(f"Found {len(substack_cookies)} Substack cookies")

            # TEST 1: Public profile
            print("\n" + "-" * 40)
            print("TEST 1: Public Profile Endpoint")
            print("-" * 40)

            test_username = username or "platformer"
            rate_limit_delay()
            profile_url = f"https://substack.com/api/v1/user/{test_username}/public_profile"
            profile_result = test_api_endpoint(page, profile_url, f"profile for @{test_username}")

            if not profile_result["success"]:
                print("\n✗ Cannot continue without profile access")
                print("  Try waiting a few minutes and running again (rate limiting)")
                input("\nPress Enter to close...")
                return

            profile = profile_result["data"]
            print(f"\n  Profile: {profile.get('name')} (ID: {profile.get('id')})")
            print(f"  Subscriptions: {len(profile.get('subscriptions', []))}")

            # Get test publication
            subs = profile.get("subscriptions", [])
            if not subs:
                print("\n✗ No subscriptions found")
                return

            subs_sorted = sorted(subs, key=lambda s: s.get("publication", {}).get("subscriber_count", 0))
            test_pub = subs_sorted[0]["publication"]
            author_id = test_pub.get("author_id") or test_pub.get("primary_user_id")
            author_handle = test_pub.get("subdomain")

            print(f"\n  Test pub: {test_pub.get('name')} ({test_pub.get('subscriber_count')} subs)")
            print(f"  Author ID: {author_id}, Handle: {author_handle}")

            # TEST 2: Direct subscriber-lists
            print("\n" + "-" * 40)
            print("TEST 2: Direct subscriber-lists Call")
            print("-" * 40)

            direct_result = {"success": False}
            if author_id:
                rate_limit_delay()
                subs_url = f"https://substack.com/api/v1/user/{author_id}/subscriber-lists?lists=subscribers"
                direct_result = test_api_endpoint(page, subs_url, "subscriber-lists (direct)")

            # TEST 3: From subscribers page
            print("\n" + "-" * 40)
            print("TEST 3: From Subscribers Page")
            print("-" * 40)

            page_result = {"success": False}
            if author_handle and author_id:
                page_result = test_from_subscribers_page(page, author_handle, author_id)

            # TEST 4: Check __NEXT_DATA__ for subscriber data
            print("\n" + "-" * 40)
            print("TEST 4: Check __NEXT_DATA__ for Subscriber Data")
            print("-" * 40)

            next_data_result = page.evaluate("""
                () => {
                    const el = document.getElementById('__NEXT_DATA__');
                    if (!el) return { found: false };

                    try {
                        const data = JSON.parse(el.textContent);
                        const pageProps = data?.props?.pageProps;

                        // Look for subscriber lists
                        const lists = pageProps?.subscriberLists ||
                                      pageProps?.initialData?.subscriberLists ||
                                      pageProps?.dehydratedState?.queries?.[0]?.state?.data?.subscriberLists;

                        if (lists) {
                            let count = 0;
                            for (const list of lists) {
                                for (const group of (list.groups || [])) {
                                    count += (group.users || []).length;
                                }
                            }
                            return { found: true, userCount: count, hasLists: true };
                        }

                        return { found: true, hasLists: false, keys: Object.keys(pageProps || {}) };
                    } catch (e) {
                        return { found: true, error: e.toString() };
                    }
                }
            """)

            if next_data_result.get("hasLists"):
                print(f"  ✓ Found {next_data_result['userCount']} users in __NEXT_DATA__!")
                print("  → This is the data source we can use")
            elif next_data_result.get("found"):
                print(f"  ⚠ __NEXT_DATA__ found but no subscriberLists")
                print(f"    Keys: {next_data_result.get('keys', [])}")
            else:
                print(f"  ✗ __NEXT_DATA__ not found")

            # TEST 5: DOM scraping fallback
            print("\n" + "-" * 40)
            print("TEST 5: DOM Scraping Fallback")
            print("-" * 40)

            dom_users = page.evaluate("""
                () => {
                    const links = document.querySelectorAll('a[href*="/@"]');
                    const handles = new Set();
                    for (const link of links) {
                        const match = link.href.match(/@([a-zA-Z0-9_-]+)/);
                        if (match) handles.add(match[1]);
                    }
                    return Array.from(handles);
                }
            """)

            if dom_users:
                print(f"  ✓ Found {len(dom_users)} unique handles in DOM")
                print(f"    Sample: {dom_users[:5]}")
            else:
                print(f"  ✗ No user handles found in DOM")

            # Summary
            print("\n" + "=" * 60)
            print("SUMMARY")
            print("=" * 60)
            print(f"Profile endpoint: {'✓' if profile_result['success'] else '✗'}")
            print(f"Direct API call: {'✓' if direct_result.get('success') else '✗ (blocked by Cloudflare)'}")
            print(f"__NEXT_DATA__: {'✓ ' + str(next_data_result.get('userCount', 0)) + ' users' if next_data_result.get('hasLists') else '✗'}")
            print(f"DOM scraping: {'✓ ' + str(len(dom_users)) + ' handles' if dom_users else '✗'}")

            if next_data_result.get("hasLists"):
                print("\n→ SUCCESS: Can get data from __NEXT_DATA__!")
                print("  Extension should navigate to subscribers pages and parse __NEXT_DATA__")
            elif dom_users:
                print("\n→ PARTIAL: Can scrape handles from DOM")
                print("  But missing full user data (bio, publication, etc.)")
            else:
                print("\n→ BLOCKED: No viable data source found")

            # Auto-close after 5 seconds
            print("\nClosing in 5 seconds...")
            time.sleep(5)

        finally:
            context.close()
            shutil.rmtree(temp_profile, ignore_errors=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("username", nargs="?", help="Substack username to test")
    parser.add_argument("--skip-extension", action="store_true", help="Skip loading extension")
    args = parser.parse_args()

    run_tests(args.username, args.skip_extension)
