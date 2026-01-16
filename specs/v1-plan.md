# PLAN: Substack Friend Finder v1

**Status:** APPROVED

## Proposed Approach

**Stack:** TypeScript + Node.js CLI

- Use `substack-api` TypeScript library for API access
- Simple JSON file cache (SQLite is overkill for MVP)
- Single entry point with modular internals
- Rate limiting with 1 req/sec default + exponential backoff

**Data flow:**
```
username → fetch subscriptions → pick top N niche newsletters
    → for each: fetch followers (capped at 100)
    → for each unique follower: fetch their subscriptions
    → compute nicheness-weighted overlap
    → filter by quality (has bio, has publication)
    → output ranked results
```

## File-Level Change List

```
substack-friend-finder/
├── package.json           # deps, scripts, bin config
├── tsconfig.json          # TypeScript config
├── src/
│   ├── index.ts           # CLI entry point, arg parsing, orchestration
│   ├── substack.ts        # API wrapper (fetch subs, followers, profiles)
│   ├── scoring.ts         # nicheness-weighted overlap calculation
│   ├── cache.ts           # JSON file cache (read/write with TTL)
│   ├── types.ts           # shared TypeScript interfaces
│   └── output.ts          # format and print results to console
├── .gitignore             # ignore node_modules, cache files, dist
└── specs/
    └── v1-friend-finder.md  # the spec
```

### File Details

| File | Purpose |
|------|---------|
| `package.json` | Dependencies: `substack-api`, `commander` (CLI args), `chalk` (colors). Scripts: `start`, `build` |
| `tsconfig.json` | Target ES2022, strict mode, output to `dist/` |
| `src/index.ts` | Parse CLI args, call orchestration flow, handle errors gracefully |
| `src/substack.ts` | Wrap `substack-api` calls with rate limiting, error handling, retries |
| `src/scoring.ts` | `computeOverlap(userSubs, candidateSubs, subCounts) → score` |
| `src/cache.ts` | `get(key)`, `set(key, value, ttl)`, persists to `.cache/substack.json` |
| `src/types.ts` | `User`, `Newsletter`, `Match`, `CacheEntry` interfaces |
| `src/output.ts` | Pretty-print matches with colors, truncate long bios |

## Test Plan

| Test Type | What | How |
|-----------|------|-----|
| **Unit** | Scoring logic | Known inputs → expected scores |
| **Unit** | Cache TTL | Set item, verify retrieval, verify expiry |
| **Integration** | Full flow | Run against a real username, verify output format |
| **Edge cases** | Empty subscriptions | User with 0 subs → graceful message |
| **Edge cases** | API failure | Mock failure → verify retry + backoff |

## Rollout / Preview Plan

1. **Local dev:** `npx ts-node src/index.ts <username>`
2. **Build:** `npm run build` → compiles to `dist/`
3. **Run compiled:** `node dist/index.js <username>`
4. **Optional:** Add `bin` to package.json for `npx substack-friends <username>`

## Definition of Done

- [ ] `npm install` succeeds
- [ ] `npx ts-node src/index.ts <username>` returns ranked matches
- [ ] Output includes: username, profile URL, overlap score, shared newsletters, bio snippet, has-publication flag
- [ ] Cache works: second run for same user is noticeably faster
- [ ] Rate limiting works: no 429 errors from Substack
- [ ] Quality filter works: results prioritize users with bios/publications
- [ ] Handles errors gracefully: bad username → helpful message, API down → retry then fail gracefully
