"""Nicheness-weighted overlap scoring for Substack subscriptions."""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

from .types import Match, Newsletter, UserProfile


def compute_nicheness_weight(subscriber_count: int) -> float:
    """
    Compute the nicheness weight for a newsletter.

    Niche newsletters (fewer subscribers) get higher weight.
    Formula: 1 / log(subscriber_count + 2)

    Examples:
        - 100 subscribers: ~0.50
        - 1,000 subscribers: ~0.33
        - 10,000 subscribers: ~0.25
        - 1,000,000 subscribers: ~0.17
    """
    # Add 2 to avoid log(0) and log(1) issues
    return 1.0 / math.log(subscriber_count + 2)


def compute_overlap_score(
    user_subs: List[Newsletter],
    candidate_subs: List[Newsletter],
) -> Tuple[float, List[Newsletter]]:
    """
    Compute the nicheness-weighted overlap score between two users' subscriptions.

    Args:
        user_subs: The input user's subscriptions
        candidate_subs: The candidate user's subscriptions

    Returns:
        Tuple of (score, list of shared newsletters sorted by nicheness)
    """
    # Build sets of subscription IDs for fast lookup
    user_sub_ids = {s.id for s in user_subs}
    candidate_sub_ids = {s.id for s in candidate_subs}

    # Find shared subscriptions
    shared_ids = user_sub_ids & candidate_sub_ids

    if not shared_ids:
        return 0.0, []

    # Get the Newsletter objects for shared subscriptions
    user_subs_by_id = {s.id: s for s in user_subs}
    shared_newsletters = [user_subs_by_id[sid] for sid in shared_ids if sid in user_subs_by_id]

    # Compute score: sum of nicheness weights
    score = sum(
        compute_nicheness_weight(n.subscriber_count)
        for n in shared_newsletters
    )

    # Sort shared newsletters by nicheness (smallest subscriber count first)
    shared_newsletters.sort(key=lambda n: n.subscriber_count)

    return score, shared_newsletters


def compute_quality_score(profile: UserProfile) -> float:
    """
    Compute a quality score for a user profile.

    Higher scores indicate more "real" users vs bots.

    Factors:
        - Has bio: +1.0
        - Has own publication: +2.0
        - Has profile photo: +0.5
    """
    score = 0.0

    if profile.bio:
        score += 1.0

    if profile.has_publication:
        score += 2.0

    if profile.photo_url:
        score += 0.5

    return score


def rank_matches(
    input_user_subs: List[Newsletter],
    candidates: List[Tuple[UserProfile, List[Newsletter]]],
    min_overlap: int = 1,
    require_bio: bool = False,
    require_publication: bool = False,
) -> List[Match]:
    """
    Rank candidate users by overlap score with quality filtering.

    Args:
        input_user_subs: The input user's subscriptions
        candidates: List of (UserProfile, subscriptions) tuples for candidates
        min_overlap: Minimum number of shared subscriptions required
        require_bio: Only include users with a bio
        require_publication: Only include users with their own publication

    Returns:
        List of Match objects sorted by score (highest first)
    """
    matches = []

    for profile, subs in candidates:
        # Apply quality filters
        if require_bio and not profile.bio:
            continue
        if require_publication and not profile.has_publication:
            continue

        # Compute overlap
        score, shared = compute_overlap_score(input_user_subs, subs)

        # Apply minimum overlap filter
        if len(shared) < min_overlap:
            continue

        # Add quality bonus to score
        quality_bonus = compute_quality_score(profile) * 0.1
        final_score = score + quality_bonus

        matches.append(Match(
            user=profile,
            score=final_score,
            shared_newsletters=shared,
        ))

    # Sort by score (descending)
    matches.sort()

    return matches
