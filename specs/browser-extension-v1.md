# Spec: Substack Friend Finder Browser Extension

## Problem / User Story

**As a** non-technical Substack user
**I want to** find people who share my niche reading interests
**So that** I can discover potential collaborators and friends without installing Python, running terminal commands, or understanding cookies

The current CLI tool works well but requires:
- Python 3.8+ installation
- Running `pip install` commands
- Terminal familiarity
- Understanding of how browser cookies work

This excludes 95%+ of potential users who would benefit from the tool.

---

## Non-Goals

1. **No backend server** - Everything runs client-side in the user's browser
2. **No cookie extraction/transmission** - Never send auth tokens to any server
3. **No account creation** - No sign-up, no email, no login to our service
4. **No data collection** - We don't store or see any user data
5. **No mobile support** - Desktop Chrome/Firefox only for v1
6. **No real-time updates** - This is a point-in-time scan, not continuous monitoring
7. **No social features** - No "connect with match" or messaging built in

---

## Constraints

### Technical
- **Browser APIs only** - Must work within extension sandbox (Manifest V3)
- **Same-origin requests** - Content script runs on `substack.com`, making API calls same-origin
- **Rate limiting** - Must respect 8-15 second delays between API requests to avoid blocks
- **Long runtime** - Full scan takes 3-10+ minutes; user must keep tab open
- **Storage limits** - `chrome.storage.local` has 10MB limit (sufficient for results)

### Compatibility
- Chrome (Manifest V3) - primary target
- Firefox (Manifest V2/3) - secondary target
- Safari - out of scope for v1

### Substack API
- No official API; using undocumented endpoints
- Endpoints may change without notice
- Subscriber/follower lists require authenticated session
- Some endpoints are Cloudflare-protected (but same-origin browser requests should pass)

---

## Acceptance Criteria

### Installation & Setup
- [ ] Extension installable from Chrome Web Store (or Firefox Add-ons)
- [ ] Zero configuration required - works immediately after install
- [ ] User must be logged into Substack in the same browser

### Core Flow
- [ ] User clicks extension icon while on any `*.substack.com` page
- [ ] Extension detects their Substack username automatically (from page/session)
- [ ] "Find Friends" button starts the scan
- [ ] Progress UI shows: current step, newsletters scanned, matches found so far
- [ ] User can switch to other tabs while scan runs (Substack tab must stay open)
- [ ] Scan completes and shows ranked results

### Results Display
- [ ] Each match shows: name, username, score, shared newsletters, bio snippet
- [ ] Clicking a match opens their Substack profile in new tab
- [ ] Results sortable by score (default), overlap count, or name
- [ ] Filter toggles: "Has bio", "Has own publication"
- [ ] Results persist in extension storage (viewable later without re-running)

### Error Handling
- [ ] Clear error if user not logged into Substack
- [ ] Clear error if user navigates away from Substack tab mid-scan
- [ ] Graceful handling of API failures (skip newsletter, continue scan)
- [ ] Rate limit detection with user-friendly message

### Performance
- [ ] Scan of 5 newsletters completes in under 5 minutes
- [ ] Partial results shown incrementally (not just at end)
- [ ] Cached results load instantly on subsequent views

---

## Risks / Unknowns + Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Cloudflare blocks same-origin requests** | Medium | High | Test thoroughly; content scripts in real browser context should pass. Fallback: reduce request rate further. |
| **Substack API changes** | Medium | High | Keep API logic modular; monitor for errors; version the extension for quick updates. |
| **Chrome Web Store rejection** | Low | Medium | Review policies carefully; avoid any mention of "scraping"; frame as "discovery tool using your own data". |
| **User closes Substack tab mid-scan** | High | Medium | Save progress to storage; allow resume. Show clear warning that tab must stay open. |
| **10+ minute scans feel broken** | High | Medium | Aggressive progress UI; show partial results; "X matches found so far". |
| **Manifest V3 service worker limits** | Medium | Medium | Keep all long-running work in content script (not background); service worker only for icon click handling. |

### Key Unknown: Will Cloudflare Allow It?
The CLI uses Playwright with stealth to bypass Cloudflare. A content script making `fetch()` from within `substack.com` *should* be treated as a legitimate user request (same cookies, same origin, real browser).

**De-risk:** Build a minimal proof-of-concept extension that just calls one subscriber-list endpoint and verify it works before full implementation.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Browser Extension                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐ │
│  │   Popup UI   │────▶│   Service    │────▶│   Content    │ │
│  │  (React/Vue) │     │   Worker     │     │   Script     │ │
│  └──────────────┘     └──────────────┘     └──────────────┘ │
│         │                                         │          │
│         │                                         ▼          │
│         │              ┌──────────────────────────────────┐  │
│         │              │     Substack API (same-origin)   │  │
│         │              │  - /api/v1/user/:id/public_profile │
│         │              │  - /api/v1/user/:id/subscriber-lists│
│         │              └──────────────────────────────────┘  │
│         │                                         │          │
│         ▼                                         ▼          │
│  ┌─────────────────────────────────────────────────────────┐│
│  │                  chrome.storage.local                   ││
│  │  - Cached results    - Scan progress    - Settings      ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Role |
|-----------|------|
| **Popup UI** | Entry point; shows "Find Friends" button, progress, and results |
| **Service Worker** | Handles extension icon click; routes messages; minimal logic |
| **Content Script** | Injected into `substack.com`; makes all API calls; runs the algorithm |
| **Storage** | Persists results, progress checkpoints, and user settings |

---

## Minimal First Slice (MVP)

### What's In
1. **Chrome extension only** (Firefox later)
2. **Manual username entry** (auto-detect later)
3. **Fixed settings**: 5 newsletters, 200 subscribers each, min 2 overlap
4. **Basic progress**: "Scanning newsletter X of Y..."
5. **Simple results list**: Name, score, shared newsletters, profile link
6. **Persist last results** (no history)

### What's Out of MVP
- Firefox support
- Auto-detect username from page
- Configurable settings (newsletter count, filters)
- Export results to file
- Result history (multiple scans)
- Resume interrupted scan
- Sorting/filtering results
- "Share this tool" or viral features

### MVP User Flow

```
1. User installs extension from Chrome Web Store
2. User goes to substack.com and logs in (if not already)
3. User clicks extension icon
4. Popup shows text input: "Enter your Substack username"
5. User enters username, clicks "Find Friends"
6. Content script is injected into page
7. Progress appears: "Fetching your subscriptions..."
8. Progress updates: "Scanning newsletter 1 of 5: [Newsletter Name]"
9. Progress updates: "Found 3 potential matches so far..."
10. Scan completes: "Done! Found 12 matches"
11. Results list appears with matches ranked by score
12. User clicks a match → opens profile in new tab
13. User closes popup; reopens later → sees cached results
```

### MVP Technical Checklist

- [ ] Chrome Manifest V3 setup
- [ ] Popup with username input + button
- [ ] Content script that can make authenticated `fetch()` to Substack API
- [ ] Port algorithm from Python: fetch subscriptions → scan newsletters → score
- [ ] Progress messages via `chrome.runtime.sendMessage`
- [ ] Results stored in `chrome.storage.local`
- [ ] Results displayed in popup
- [ ] Basic error handling (not logged in, API failures)

---

## Open Questions

1. **Username auto-detection**: Can we reliably extract the logged-in user's username from the Substack page DOM or a cookie? This would eliminate the manual entry step.

2. **Cloudflare behavior**: Does `fetch()` from a content script on `substack.com` get treated the same as a regular page request? Need to verify with POC.

3. **Rate limit signals**: How does Substack signal rate limiting? 429 status? Cloudflare challenge page? Need to handle gracefully.

4. **Chrome Web Store approval**: What's the review timeline? Any policy concerns with "reading subscriber data" even though it's user's own data in their own browser?
