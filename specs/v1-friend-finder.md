# SPEC: Substack Friend Finder v1

## Problem / User Story

As a Substack reader, I want to find other people who share my niche reading interests, so I can discover potential collaborators, conversation partners, or friends with aligned intellectual curiosity.

**The insight:** If two people both subscribe to an obscure 500-subscriber philosophy newsletter, that's a stronger affinity signal than both reading The Hustle (1M+ subscribers). We weight overlap by nicheness.

**Use case:** Finding people to have video calls with, potential collaborators, interesting internet friends.

## Non-Goals

- **Not a recommendation engine** — we suggest *people*, not newsletters
- **Not social networking** — no messaging, profiles, or features beyond matching
- **Not a scraper at scale** — this is a personal tool, not a service

## Constraints

| Constraint | Detail |
|------------|--------|
| Data access | Unofficial Substack API (TypeScript library has best coverage) |
| User enumeration | Via followers of newsletters (public by default, cannot be hidden) |
| Rate limits | ~1 req/sec to be safe; aggressive caching required |
| No official API | Endpoints may change; need defensive coding |

## How It Works

### User Enumeration Strategy

Substack's follower lists are **public by default**. Followers include:
- All free subscribers
- All paid subscribers
- People who follow just for Notes

We traverse the graph:
1. Input user → their subscriptions (newsletters they follow)
2. Each newsletter → its followers list
3. Each follower → their subscriptions
4. Compute overlap scores

### Overlap Scoring

Simple set overlap is naive — subscribing to the same mega-popular newsletter is weak signal.

**Nicheness-weighted scoring:**
```
score = Σ (1 / log(subscriber_count + 1)) for each shared subscription
```

- Sharing a 100-subscriber newsletter: `1/log(101) ≈ 0.50`
- Sharing a 1M-subscriber newsletter: `1/log(1000001) ≈ 0.17`

This weights niche overlap ~3x more than mainstream overlap.

### Quality Filters

To avoid bots and low-quality matches, prioritize users who:
- Have a bio filled out
- Have their own Substack publication (fellow creators)
- Have profile photo set
- Follow a reasonable number of newsletters (not 0, not 10,000)

## Acceptance Criteria

1. User enters Substack username → system fetches their subscriptions
2. For each subscription (up to configurable limit), fetch follower list
3. For each follower, fetch their subscriptions
4. Compute nicheness-weighted overlap score
5. Filter/rank by quality signals (has bio, has publication, etc.)
6. Output: ranked list with score, shared newsletters, profile link, bio snippet

## Risks / Unknowns

| Risk | Mitigation |
|------|------------|
| API changes/breaks | Abstract API calls; cache aggressively |
| Rate limiting | 1 req/sec default; exponential backoff; resume capability |
| Follower lists very large | Cap at N followers per newsletter; sample randomly |
| Subscriber counts unavailable | Use follower count as proxy, or default weight |
| Privacy concerns | Only accessing public data; tool is for personal use |

## Minimal First Slice (MVP)

**CLI tool in TypeScript (better API library support)**

```
npx substack-friends <username>
```

1. Fetch user's subscriptions
2. Pick top 5 subscriptions by nicheness (smallest subscriber counts)
3. For each, fetch up to 100 followers
4. For each unique follower, fetch their subscriptions
5. Score and rank
6. Output top 20 matches with:
   - Username + profile URL
   - Overlap score
   - Shared newsletters (sorted by nicheness)
   - Bio snippet (if available)
   - Whether they have their own publication

**Caching:** SQLite or JSON file to avoid re-fetching on subsequent runs.

## Future Possibilities (Out of Scope for v1)

- Web UI for non-technical users
- "Mutual match" detection (they'd also rank you highly)
- Integration with calendar for scheduling intro calls
- Filtering by topic/category of shared newsletters
