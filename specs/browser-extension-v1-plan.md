# Implementation Plan: Substack Friend Finder Browser Extension

> Based on: `specs/browser-extension-v1.md`

## Proposed Approach

### Phase 0: Proof of Concept (De-risk Cloudflare)
Before building the full extension, validate that content script `fetch()` calls work for authenticated Substack endpoints. This is the biggest technical risk.

### Phase 1: Extension Scaffolding
Set up Chrome Manifest V3 structure, build tooling, and basic popup UI.

### Phase 2: Core Algorithm Port
Port the Python algorithm to TypeScript, running in the content script.

### Phase 3: UI & Messaging
Wire up popup ↔ content script communication, progress updates, and results display.

### Phase 4: Polish & Publish
Error handling, edge cases, Chrome Web Store submission.

### Post-MVP: Nice Results Page
After MVP ships, add a dedicated results page (new tab) with better visuals.

---

## File-Level Change List

### New Directory Structure

```
extension/
├── manifest.json           # Chrome Manifest V3 config
├── package.json            # Build dependencies (TypeScript, bundler)
├── tsconfig.json           # TypeScript config
├── vite.config.ts          # Vite bundler config (or webpack)
├── src/
│   ├── popup/
│   │   ├── popup.html      # Popup entry point
│   │   ├── popup.ts        # Popup logic
│   │   └── popup.css       # Popup styles
│   ├── content/
│   │   ├── content.ts      # Content script (runs on substack.com)
│   │   ├── api.ts          # Substack API client (fetch-based)
│   │   ├── algorithm.ts    # Friend-finding algorithm (ported from Python)
│   │   └── scoring.ts      # Nicheness scoring (ported from Python)
│   ├── background/
│   │   └── service-worker.ts   # Minimal service worker
│   ├── shared/
│   │   ├── types.ts        # Shared TypeScript types
│   │   ├── storage.ts      # chrome.storage helpers
│   │   └── messages.ts     # Message type definitions
│   └── results/            # (Post-MVP)
│       ├── results.html    # Full-page results view
│       ├── results.ts
│       └── results.css
├── assets/
│   ├── icon-16.png
│   ├── icon-48.png
│   └── icon-128.png
└── dist/                   # Built output (gitignored)
```

### File Details

| File | Purpose | Lines (est.) |
|------|---------|--------------|
| `manifest.json` | Extension config: permissions, content scripts, popup | ~40 |
| `popup.html` | Simple HTML shell for popup | ~20 |
| `popup.ts` | Popup state management, form handling, results display | ~200 |
| `popup.css` | Popup styling (compact, clean) | ~150 |
| `content.ts` | Entry point for content script, message handling | ~100 |
| `api.ts` | Substack API calls: profile, subscriptions, subscribers, followers | ~150 |
| `algorithm.ts` | Two-phase algorithm: collection + scoring | ~150 |
| `scoring.ts` | `computeNichenessWeight`, `scoreByAppearances` | ~80 |
| `service-worker.ts` | Icon click handling, message routing | ~30 |
| `types.ts` | `UserProfile`, `Newsletter`, `Match`, etc. | ~50 |
| `storage.ts` | Helpers for `chrome.storage.local` | ~40 |
| `messages.ts` | Message types for popup ↔ content script | ~30 |

**Total new code: ~1,000 lines**

---

## Detailed Implementation Steps

### Phase 0: Proof of Concept (~1 hour)

**Goal:** Verify `fetch()` from content script works for authenticated endpoints.

1. Create minimal extension with just:
   - `manifest.json` with content script on `*.substack.com`
   - `content.ts` that calls `/api/v1/user/{username}/subscriber-lists`
   - Log response to console

2. Load unpacked in Chrome, go to substack.com (logged in), check console.

3. **If blocked:** Try reducing to single endpoint, adding delays, or using `XMLHttpRequest` instead.

4. **If works:** Proceed to Phase 1.

---

### Phase 1: Extension Scaffolding

#### 1.1 Project Setup
- [ ] Create `extension/` directory
- [ ] Initialize `package.json` with dependencies:
  - `typescript`
  - `vite` + `@crxjs/vite-plugin` (or `webpack`)
  - `@anthropic-ai/sdk` (dev only, for testing? no, not needed)
- [ ] Create `tsconfig.json` with strict mode
- [ ] Create `vite.config.ts` for extension bundling

#### 1.2 Manifest V3
- [ ] Create `manifest.json`:
  ```json
  {
    "manifest_version": 3,
    "name": "Substack Friend Finder",
    "version": "0.1.0",
    "description": "Find people who share your niche reading interests on Substack",
    "permissions": ["storage", "activeTab"],
    "host_permissions": ["*://*.substack.com/*"],
    "action": {
      "default_popup": "popup.html",
      "default_icon": { "16": "icon-16.png", "48": "icon-48.png", "128": "icon-128.png" }
    },
    "content_scripts": [{
      "matches": ["*://*.substack.com/*"],
      "js": ["content.js"]
    }],
    "background": {
      "service_worker": "service-worker.js"
    }
  }
  ```

#### 1.3 Basic Popup
- [ ] Create `popup.html` with:
  - Username input field
  - "Find Friends" button
  - Progress area (hidden initially)
  - Results area (hidden initially)
- [ ] Create `popup.css` with minimal styling
- [ ] Create `popup.ts` with form submission handler

#### 1.4 Stub Content Script
- [ ] Create `content.ts` that listens for messages
- [ ] Create `service-worker.ts` (empty for now)

#### 1.5 Build & Test
- [ ] Configure Vite to output to `dist/`
- [ ] Load unpacked extension in Chrome
- [ ] Verify popup opens, can type username

---

### Phase 2: Core Algorithm Port

#### 2.1 Types
- [ ] Create `types.ts`:
  ```typescript
  interface UserProfile {
    id: number;
    username: string;
    name: string;
    bio?: string;
    photoUrl?: string;
    hasPublication: boolean;
    publicationUrl?: string;
  }

  interface Newsletter {
    id: number;
    name: string;
    subdomain: string;
    authorId: number;
    subscriberCount: number;
  }

  interface Match {
    user: UserProfile;
    score: number;
    sharedNewsletters: Newsletter[];
  }
  ```

#### 2.2 API Client
- [ ] Create `api.ts` with:
  - `getUserProfile(username: string): Promise<UserProfile>`
  - `getUserSubscriptions(username: string): Promise<Newsletter[]>`
  - `getAuthorHandle(subdomain: string): Promise<string>`
  - `getSubscribers(authorHandle: string, limit: number): Promise<UserProfile[]>`
  - `getFollowers(authorHandle: string, limit: number): Promise<UserProfile[]>`
- [ ] Add rate limiting: 8-15 second random delays between requests
- [ ] Add error handling: retry once on failure, then skip

#### 2.3 Scoring
- [ ] Create `scoring.ts`:
  - `computeNichenessWeight(subscriberCount: number): number`
  - `computeQualityScore(profile: UserProfile): number`
  - `scoreByAppearances(candidates: Map, minOverlap: number): Match[]`

#### 2.4 Algorithm
- [ ] Create `algorithm.ts`:
  - `findFriends(username: string, onProgress: callback): Promise<Match[]>`
  - Implements two-phase algorithm from Python CLI
  - Calls `onProgress` with status updates

---

### Phase 3: UI & Messaging

#### 3.1 Message Types
- [ ] Create `messages.ts`:
  ```typescript
  type Message =
    | { type: 'START_SCAN'; username: string }
    | { type: 'PROGRESS'; step: string; detail: string; matchCount: number }
    | { type: 'COMPLETE'; matches: Match[] }
    | { type: 'ERROR'; message: string };
  ```

#### 3.2 Content Script Integration
- [ ] Update `content.ts` to:
  - Listen for `START_SCAN` message
  - Call `findFriends()` with progress callback
  - Send `PROGRESS` messages back to popup
  - Send `COMPLETE` or `ERROR` when done

#### 3.3 Popup Updates
- [ ] Update `popup.ts` to:
  - Send `START_SCAN` to content script on button click
  - Listen for `PROGRESS` messages, update UI
  - Listen for `COMPLETE`, display results
  - Listen for `ERROR`, show error message

#### 3.4 Storage
- [ ] Create `storage.ts`:
  - `saveResults(matches: Match[]): Promise<void>`
  - `loadResults(): Promise<Match[] | null>`
  - `clearResults(): Promise<void>`
- [ ] On popup open: check for cached results, display if present
- [ ] On scan complete: save results to storage

#### 3.5 Results Display
- [ ] In popup, render results list:
  - Profile photo (or placeholder)
  - Name + username
  - Score badge
  - Shared newsletters (comma-separated)
  - Bio snippet (truncated)
  - Click → open profile in new tab

---

### Phase 4: Polish & Publish

#### 4.1 Error Handling
- [ ] "Not on Substack" error if popup opened on other site
- [ ] "Not logged in" detection (check if subscriber-lists returns 401/403)
- [ ] "Rate limited" detection and user-friendly message
- [ ] "Username not found" handling

#### 4.2 Edge Cases
- [ ] User has no subscriptions
- [ ] All newsletters are too large (no niche ones)
- [ ] Zero matches found
- [ ] Network errors mid-scan

#### 4.3 UX Polish
- [ ] Loading spinner during scan
- [ ] "Keep this tab open" warning
- [ ] "Run again" button to clear cache and rescan
- [ ] Timestamp on cached results ("Last scanned: 2 hours ago")

#### 4.4 Chrome Web Store
- [ ] Create promotional images (1280x800, 440x280)
- [ ] Write store description
- [ ] Create privacy policy (hosted on GitHub Pages or similar)
- [ ] Submit for review

---

### Post-MVP: Nice Results Page

- [ ] Create `results.html` as a full-page view
- [ ] Open in new tab after scan completes (or via "View Full Results" button)
- [ ] Better layout: cards, filters, sorting
- [ ] Export to CSV/JSON
- [ ] Share buttons (copy link to tool, not to results)

---

## Test Plan

### Manual Testing Checklist

#### Installation
- [ ] Load unpacked extension in Chrome
- [ ] Extension icon appears in toolbar
- [ ] Popup opens when clicked

#### Happy Path
- [ ] Enter valid username on substack.com
- [ ] Scan starts, progress updates appear
- [ ] Scan completes with matches
- [ ] Matches display correctly (name, score, shared newsletters)
- [ ] Clicking match opens profile in new tab
- [ ] Close popup, reopen → cached results shown

#### Error Cases
- [ ] Enter invalid username → "User not found" error
- [ ] Open popup on non-Substack site → "Go to substack.com" message
- [ ] Log out of Substack, try scan → "Please log in" error
- [ ] Disconnect network mid-scan → graceful error, partial results if any

#### Edge Cases
- [ ] User with 0 subscriptions → "No subscriptions found"
- [ ] User with only huge newsletters → fewer matches, still works
- [ ] User with 100+ subscriptions → scans top 5 nichest

### Automated Testing
- [ ] Unit tests for `scoring.ts` (port Python test cases if any)
- [ ] Unit tests for `algorithm.ts` with mocked API responses
- [ ] Integration tests deferred (would need Substack test account)

---

## Rollout / Preview Plan

### Stage 1: Internal Testing
- Load unpacked extension
- Test with 2-3 real Substack accounts
- Fix bugs, iterate

### Stage 2: Friends & Family
- Distribute as `.zip` for manual install
- Get feedback from 5-10 non-technical users
- Focus on UX confusion, error messages

### Stage 3: Chrome Web Store (Unlisted)
- Submit for review
- Share unlisted link with beta testers
- Monitor for issues

### Stage 4: Public Launch
- Make listing public
- Announce on Twitter/Substack Notes
- Monitor reviews and feedback

---

## Definition of Done

MVP is complete when:

1. **Installable**: Extension can be loaded unpacked (and ideally published to Chrome Web Store)
2. **Functional**: User can enter username, run scan, see matches
3. **Progress**: User sees progress updates during 3-10 minute scan
4. **Results**: Matches displayed with name, score, shared newsletters, profile link
5. **Persistence**: Results cached; reopening popup shows last results
6. **Errors**: Clear error messages for common failures (not logged in, user not found, network error)
7. **Privacy**: Zero data sent to any server; all processing client-side

---

## Estimated Effort

| Phase | Effort |
|-------|--------|
| Phase 0: POC | ~1 hour |
| Phase 1: Scaffolding | ~2 hours |
| Phase 2: Algorithm Port | ~3 hours |
| Phase 3: UI & Messaging | ~3 hours |
| Phase 4: Polish | ~2 hours |
| Chrome Web Store submission | ~1 hour |
| **Total MVP** | **~12 hours** |
| Post-MVP: Nice Results Page | ~3 hours |

---

## Open Decisions

1. **Bundler choice**: Vite with `@crxjs/vite-plugin` vs Webpack. Recommendation: Vite (simpler, faster).

2. **UI framework**: Plain TypeScript vs Preact/React. Recommendation: Plain TS for MVP (popup is simple enough).

3. **Results page**: Open automatically after scan, or require button click? Recommendation: Button click for MVP, auto-open post-MVP.

---

**Approve? (yes/no)**
