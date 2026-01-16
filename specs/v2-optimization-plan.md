# PLAN: Substack Friend Finder v2 - Algorithm Optimization

**Status:** PENDING APPROVAL

## The Problem

The current algorithm is fundamentally inefficient:

```
Current flow:
1. Get user's subscriptions (N newsletters)
2. For each newsletter, get subscribers/followers (~200 people each)
3. For EACH person found, fetch their full subscription list  ← BOTTLENECK
4. Compute overlap
```

**The math:**
- 28 newsletters × 200 people = 5,600 people
- 5,600 API calls × 4 seconds each = **6+ hours**

Even with perfect rate limiting, this approach doesn't scale.

## Key Insight

From the original spec: *"If two people both subscribe to an obscure 500-subscriber philosophy newsletter, that's a stronger affinity signal."*

**Critical realization:** If someone appears in the follower lists of MULTIPLE of the user's newsletters, they *already* have demonstrated overlap. We don't need to fetch their full subscription list to know they share interests.

The count of "how many of my newsletters does this person also follow" IS a valid overlap metric — and it's essentially free since we're already collecting that data.

## Proposed Approach: Two-Phase Algorithm

### Phase 1: Collection (Fast)
Scan all newsletters, collect all people, track which newsletters each person appears in.

```
person_appearances: Dict[user_id, List[Newsletter]]
```

### Phase 2: Scoring (Instant)
Score by the newsletters we ALREADY KNOW they follow:

```
score = Σ (1 / log(subscriber_count + 1)) for each of user's newsletters they appear in
```

No additional API calls needed!

### Phase 3: Optional Enrichment (Bounded)
For the TOP K candidates only (e.g., top 50), optionally fetch their full subscription list to:
- Find additional shared newsletters beyond the ones we scanned
- Refine scores for final ranking

This bounds the expensive API calls to a constant K, not O(N × M).

## Complexity Comparison

| Step | Current | Optimized |
|------|---------|-----------|
| Get user's subs | 1 call | 1 call |
| Get newsletter followers | N calls | N calls |
| Get candidate subs | **N × M calls** | **K calls** (optional) |
| **Total** | ~5,600 calls | ~56 calls + optional 50 |

**Time estimate:**
- Current: 6+ hours
- Optimized: ~15-20 minutes (mostly browser navigation delays)

## File-Level Change List

### Modified Files

| File | Changes |
|------|---------|
| `src/main.py` | Rewrite `find_friends()` to use two-phase algorithm |
| `src/scoring.py` | Add `score_by_appearances()` function for Phase 2 scoring |
| `src/types.py` | Add `CandidateAppearances` type to track person → newsletters mapping |
| `src/output.py` | Update to show "appears in X newsletters" in output |

### New Files

None — this is a refactor, not new functionality.

### Detailed Changes

**`src/main.py`:**
```python
def find_friends(...):
    # Phase 1: Collection
    person_newsletters: Dict[int, Tuple[UserProfile, List[Newsletter]]] = {}

    for newsletter in newsletters_to_scan:
        people = get_subscribers_and_followers(newsletter)
        for person in people:
            if person.id not in person_newsletters:
                person_newsletters[person.id] = (person, [])
            person_newsletters[person.id][1].append(newsletter)

    # Phase 2: Score by appearances (no API calls!)
    matches = score_by_appearances(
        user_newsletters=input_subs,
        candidates=person_newsletters,
        min_overlap=min_overlap,
    )

    # Phase 3: Optional enrichment for top K
    # (can be skipped for speed, or enabled with --enrich flag)
```

**`src/scoring.py`:**
```python
def score_by_appearances(
    user_newsletters: List[Newsletter],
    candidates: Dict[int, Tuple[UserProfile, List[Newsletter]]],
    min_overlap: int = 2,
) -> List[Match]:
    """Score candidates by how many of user's newsletters they appear in."""
    matches = []
    for user_id, (profile, appeared_in) in candidates.items():
        if len(appeared_in) < min_overlap:
            continue

        # Nicheness-weighted score
        score = sum(1 / math.log(n.subscriber_count + 2) for n in appeared_in)

        matches.append(Match(
            user=profile,
            score=score,
            shared_newsletters=appeared_in,
        ))

    return sorted(matches, key=lambda m: m.score, reverse=True)
```

## Test Plan

| Test | Description |
|------|-------------|
| **Unit: scoring** | Verify `score_by_appearances()` correctly weights by nicheness |
| **Integration** | Run with 5 newsletters, verify results in <5 minutes |
| **Full scan** | Run with 28 newsletters, verify completes in <30 minutes |
| **Comparison** | Spot-check that top matches are reasonable (manual review) |

## Rollout Plan

1. Create feature branch from current state
2. Implement two-phase algorithm
3. Test with small newsletter count (3-5)
4. Test with full newsletter count (28)
5. Compare results quality with previous approach
6. Remove old code paths and debug output
7. PR with clean summary

## Definition of Done

- [ ] Full scan of 28 newsletters completes in under 30 minutes
- [ ] Results are saved to a file (not just displayed)
- [ ] No 429 rate limit errors during scan
- [ ] Top matches have overlap of 2+ newsletters
- [ ] Output shows which shared newsletters were detected
- [ ] Optional `--enrich` flag to fetch full subscriptions for top K

## Trade-offs

**What we lose:**
- Can't find shared newsletters that weren't in the scanned set
  - Mitigation: Scan more newsletters, or use `--enrich` for top candidates

**What we gain:**
- 100x+ faster execution
- Actually usable for real scans
- No rate limiting issues

## Alternative Considered

**"Just add more delays and let it run overnight"**
- Rejected because: Unreliable (Cloudflare may block mid-run), poor UX, doesn't scale

---

**Approve? (yes/no)**
