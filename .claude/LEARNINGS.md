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
