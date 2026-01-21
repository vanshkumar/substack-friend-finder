# Learnings

## Substack API Access

- **No official public API** — Substack doesn't provide one and has no timeline for it
- **Unofficial TypeScript library** (`substack-api` by jakub-k-slys) has best coverage:
  - Can get user subscriptions
  - Can get post comments with author profiles
  - Can get newsletter metadata
  - Docs: https://substack-api.readthedocs.io/
- **Unofficial Python library** (`substack-api` on PyPI by NHagar) is more limited:
  - Has `user.get_subscriptions()`
  - Does NOT have comment fetching built-in
- **Rate limit:** 8-15 second delays between browser requests to avoid detection

## Substack Data Model

- **Followers vs Subscribers:**
  - Subscribers (free or paid) automatically become followers
  - Followers is the superset — includes subscribers + people who just follow for Notes
  - **Followers list is PUBLIC by default and cannot be hidden**
- **Likers:** Visible on free posts (click like count → see profiles), but some users opt out
- **Commenters:** Comments include `author: Profile` with `slug` (username)

## User Enumeration Strategy

Since there's no way to enumerate "all Substack users", we traverse the graph:
1. Input user → their subscriptions
2. Each newsletter → its followers (public)
3. Each follower → their subscriptions
4. Compute overlap

This captures engaged readers without needing a master user list.

## Quality Signals for Real Users (vs Bots)

- Has bio filled out
- Has their own Substack publication
- Has profile photo
- Reasonable number of subscriptions (not 0, not 10,000)

## Cloudflare Bypass

- Direct HTTP requests to Substack API get **403 Forbidden** due to Cloudflare
- **Playwright with non-headless Firefox** bypasses this:
  - Use `headless=False` (Cloudflare detects headless mode)
  - Firefox works better than Chromium for Cloudflare compatibility
  - Auto-extract cookies from user's Firefox/Chrome/Safari via `browser_cookie3` (no manual cookie file needed)
  - Uses `playwright-stealth` for additional bot detection evasion
  - Rate limiting: 8-15 second random delays between requests to appear human
  - Intercepts API responses when navigating to subscribers/followers pages

## Subscriber Lists API

- Endpoint: `https://substack.com/api/v1/user/{user_id}/subscriber-lists?lists=subscribers`
- **Response structure is nested:**
  ```json
  {
    "subscriberLists": [{
      "groups": [{
        "name": "Paid subscribers",
        "users": [...]
      }, {
        "name": "Free subscribers",
        "users": [...]
      }]
    }]
  }
  ```
- Users array contains: `id`, `name`, `handle`, `photo_url`, `bio`, `primaryPublication`, `followerCount`
- Requires being subscribed to the publication to access

## Python Environment Issues

- Multiple Python installations can cause `ModuleNotFoundError` even after `pip install`
- Check with `which python3` and `python3 -c "import sys; print(sys.executable)"`
- Use explicit path like `/opt/miniconda3/bin/python3` when needed

## Browser Extension Approach

- **Content scripts run in an ISOLATED WORLD** - this is critical:
  - Content scripts do NOT share the page's JavaScript context
  - `fetch()` from content script does NOT include page cookies automatically
  - This causes CORS/auth failures when trying to hit authenticated endpoints
- **Solution: Inject a script into the page's MAIN context:**
  - Create a separate `injected.js` file
  - Use `document.createElement('script')` to inject it into the DOM
  - The injected script runs in the page's context with access to cookies
  - Communicate between content script and injected script via `window.postMessage`
  - Mark injected.js in manifest's `web_accessible_resources`
- **Manifest V3** requirements:
  - Use `service_worker` instead of `background.scripts`
  - `host_permissions` separate from `permissions`
  - Content scripts declared in manifest, not programmatically injected
- **Long-running operations** must stay in content script:
  - Service workers have execution time limits
  - Content script lives as long as the page is open
  - User must keep Substack tab open during scan
- **Message passing:**
  - Popup ↔ Content: `chrome.tabs.sendMessage` and `chrome.runtime.sendMessage`
  - Content script can send progress updates back to popup
  - Results stored in `chrome.storage.local` (10MB limit, sufficient for our use)
- **Key API endpoints from content script:**
  - `/api/v1/user/{username}/public_profile` - profile + subscriptions
  - `/api/v1/reader/subscriber-lists/{author_handle}?list=followers` - authenticated
  - `https://{subdomain}.substack.com/api/v1/publication` - get author handle

## Cloudflare Detection

- **Playwright is detected as automation** even with cookies/stealth
- Direct `fetch()` calls from injected scripts get 403 Cloudflare challenge
- **Real browser extensions are NOT blocked** - they run in actual Chrome/Firefox
- Testing strategy: Can't fully test with Playwright; must test extension in real browser
- The extension's approach of navigating + scraping __NEXT_DATA__ should work in real Chrome

## Getting Subscriber Data in Browser Extensions

- **DOM scraping only gets visible users** - Substack lazy-loads more on scroll
- **__NEXT_DATA__ contains initial server-rendered data** but may not have all users
- **Interception doesn't work** - Substack's CSP blocks inline scripts, and external scripts load too late
- **Solution: Make direct API calls** from injected script:
  - Endpoint: `https://substack.com/api/v1/user/{authorId}/subscriber-lists?lists=subscribers`
  - Or `lists=followers` for followers
  - Works because injected script runs in page context with cookies
  - Falls back to __NEXT_DATA__ then DOM scraping if API fails
- **Data priority**: 1) Direct API call, 2) __NEXT_DATA__, 3) DOM scraping
- The subscriber-lists API returns all users, not just visible ones
