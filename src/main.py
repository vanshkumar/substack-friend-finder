"""Main CLI entry point for Substack Friend Finder."""

from __future__ import annotations

import argparse
import sys
from typing import Dict, List, Tuple

from . import output
from . import substack_client as client
from .browser import init_browser, get_publication_subscribers_browser, get_publication_followers_browser, close_browser
from .scoring import score_by_appearances
from .types import Newsletter, UserProfile


def find_friends(
    username: str,
    max_newsletters: int = 5,
    subscribers_per_newsletter: int = 200,
    min_overlap: int = 2,
    require_bio: bool = False,
    require_publication: bool = False,
    limit: int = 20,
    output_file: str = None,
) -> None:
    """
    Find friends based on Substack subscription overlap.

    Uses a two-phase algorithm:
    1. Collection: Scan newsletters, track which newsletters each person appears in
    2. Scoring: Score by appearances (no additional API calls needed)

    Args:
        username: The Substack username to find friends for
        max_newsletters: Maximum number of newsletters to scan
        subscribers_per_newsletter: Maximum subscribers to fetch per newsletter
        min_overlap: Minimum number of shared newsletters for a match
        require_bio: Only show users with a bio
        require_publication: Only show users with their own publication
        limit: Maximum number of matches to display
        output_file: Optional file path to save results
    """
    output.print_header(username)

    # Initialize browser for authenticated API access
    output.print_progress("Initializing browser...")
    if not init_browser():
        output.print_error("Failed to initialize browser. Make sure you're logged into Substack in Firefox/Chrome.")
        return

    try:
        # Step 1: Get the input user's profile
        output.print_progress(f"Fetching profile for @{username}...")
        input_profile = client.get_user_profile(username)

        if not input_profile:
            output.print_error(f"Could not find user @{username}")
            return

        # Step 2: Get the input user's subscriptions
        output.print_progress("Fetching subscriptions...")
        input_subs = client.get_user_subscriptions(username)

        if not input_subs:
            output.print_error(f"Could not fetch subscriptions for @{username}")
            return

        output.print_progress(f"Found {len(input_subs)} subscriptions")

        # Step 3: Filter to newsletters with author_id and sort by subscriber count (nichest first)
        newsletters_with_author = [n for n in input_subs if n.author_id]
        sorted_subs = sorted(newsletters_with_author, key=lambda n: n.subscriber_count)
        newsletters_to_scan = sorted_subs[:max_newsletters]

        output.print_progress(
            f"Scanning {len(newsletters_to_scan)} newsletters (sorted by nicheness)..."
        )

        # ============================================================
        # PHASE 1: COLLECTION
        # Scan all newsletters, track which newsletters each person appears in
        # ============================================================

        # Dict: user_id -> (UserProfile, List[Newsletter they appeared in])
        person_appearances: Dict[int, Tuple[UserProfile, List[Newsletter]]] = {}
        newsletters_scanned = 0

        for i, newsletter in enumerate(newsletters_to_scan, 1):
            output.print_progress(
                f"  [{i}/{len(newsletters_to_scan)}] {newsletter.name} ({newsletter.subscriber_count:,} subs)"
            )

            # Get author handle first (needed for both subscribers and followers)
            from .browser import _get_author_handle
            author_handle = _get_author_handle(newsletter.subdomain) if newsletter.subdomain else None

            if not author_handle:
                output.print_progress(f"    Could not find author handle, skipping...")
                newsletters_scanned += 1
                continue

            # Get subscribers of this newsletter via browser
            subscribers = get_publication_subscribers_browser(
                author_handle,
                limit=subscribers_per_newsletter,
            )

            # Get followers of this newsletter via browser
            followers = get_publication_followers_browser(
                author_handle,
                limit=subscribers_per_newsletter,
            )

            # Combine subscribers and followers (avoiding duplicates)
            seen_ids = set()
            combined = []
            for person in subscribers + followers:
                if person.id not in seen_ids:
                    seen_ids.add(person.id)
                    combined.append(person)

            output.print_progress(
                f"    Found {len(combined)} unique people ({len(subscribers)} subs + {len(followers)} followers)"
            )

            # Track which newsletters each person appears in
            for person in combined:
                # Skip the input user
                if input_profile and person.id == input_profile.id:
                    continue

                if person.id not in person_appearances:
                    person_appearances[person.id] = (person, [])

                # Add this newsletter to their appearance list
                person_appearances[person.id][1].append(newsletter)

            newsletters_scanned += 1

        # ============================================================
        # PHASE 2: SCORING
        # Score candidates by newsletters they appear in (no API calls!)
        # ============================================================

        output.print_progress(f"\nScoring {len(person_appearances)} unique candidates...")

        matches = score_by_appearances(
            candidates=person_appearances,
            min_overlap=min_overlap,
            require_bio=require_bio,
            require_publication=require_publication,
        )

        # Step 6: Output results
        output.print_summary(
            input_username=username,
            num_subscriptions=len(input_subs),
            num_newsletters_scanned=newsletters_scanned,
            num_candidates=len(person_appearances),
            num_matches=len(matches),
        )

        output.print_matches(matches, limit=limit)

        # Save to file if requested
        if output_file:
            save_results_to_file(matches, output_file, username, len(input_subs), newsletters_scanned)
            output.print_progress(f"\nResults saved to {output_file}")

    finally:
        close_browser()


def save_results_to_file(
    matches: list,
    filepath: str,
    username: str,
    num_subs: int,
    num_scanned: int,
) -> None:
    """Save match results to a text file."""
    with open(filepath, "w") as f:
        f.write(f"Substack Friend Finder Results for @{username}\n")
        f.write(f"=" * 50 + "\n\n")
        f.write(f"User's subscriptions: {num_subs}\n")
        f.write(f"Newsletters scanned: {num_scanned}\n")
        f.write(f"Total matches: {len(matches)}\n\n")
        f.write("-" * 50 + "\n\n")

        for i, match in enumerate(matches, 1):
            user = match.user
            f.write(f"#{i} {user.name or user.username}")
            if user.username:
                f.write(f" (@{user.username})")
            f.write(f"\n")
            f.write(f"   Score: {match.score:.2f}\n")
            f.write(f"   Profile: https://substack.com/@{user.username}\n")

            if user.has_publication and user.publication_url:
                f.write(f"   Publication: {user.publication_url}\n")

            shared_names = [n.name for n in match.shared_newsletters]
            f.write(f"   Shared ({len(shared_names)}): {', '.join(shared_names)}\n")

            if user.bio:
                bio_short = user.bio[:150] + "..." if len(user.bio) > 150 else user.bio
                bio_short = bio_short.replace("\n", " ")
                f.write(f"   Bio: {bio_short}\n")

            f.write("\n")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Find friends based on Substack subscription overlap",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.main johndoe
  python -m src.main johndoe --max-newsletters 10 --require-publication
  python -m src.main johndoe --max-newsletters 28 --output results.txt
        """,
    )

    parser.add_argument(
        "username",
        help="Substack username to find friends for",
    )
    parser.add_argument(
        "--max-newsletters",
        type=int,
        default=5,
        help="Maximum number of newsletters to scan (default: 5)",
    )
    parser.add_argument(
        "--subscribers-per-newsletter",
        type=int,
        default=200,
        help="Maximum subscribers to fetch per newsletter (default: 200)",
    )
    parser.add_argument(
        "--min-overlap",
        type=int,
        default=2,
        help="Minimum shared newsletters for a match (default: 2)",
    )
    parser.add_argument(
        "--require-bio",
        action="store_true",
        help="Only show users with a bio",
    )
    parser.add_argument(
        "--require-publication",
        action="store_true",
        help="Only show users with their own publication",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum matches to display (default: 20)",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        help="Save results to file",
    )

    args = parser.parse_args()

    try:
        find_friends(
            username=args.username,
            max_newsletters=args.max_newsletters,
            subscribers_per_newsletter=args.subscribers_per_newsletter,
            min_overlap=args.min_overlap,
            require_bio=args.require_bio,
            require_publication=args.require_publication,
            limit=args.limit,
            output_file=args.output,
        )
    except KeyboardInterrupt:
        output.console.print("\n[yellow]Interrupted by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        output.print_error(str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
