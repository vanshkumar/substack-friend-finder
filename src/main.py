"""Main CLI entry point for Substack Friend Finder."""

from __future__ import annotations

import argparse
import sys
from typing import Dict, List, Tuple

from . import output
from . import substack_client as client
from .browser import init_browser, get_publication_subscribers_browser, close_browser
from .scoring import rank_matches
from .types import Newsletter, UserProfile


def find_friends(
    username: str,
    max_newsletters: int = 5,
    subscribers_per_newsletter: int = 50,
    min_overlap: int = 2,
    require_bio: bool = False,
    require_publication: bool = False,
    limit: int = 20,
) -> None:
    """
    Find friends based on Substack subscription overlap.

    Args:
        username: The Substack username to find friends for
        max_newsletters: Maximum number of newsletters to scan
        subscribers_per_newsletter: Maximum subscribers to fetch per newsletter
        min_overlap: Minimum number of shared subscriptions for a match
        require_bio: Only show users with a bio
        require_publication: Only show users with their own publication
        limit: Maximum number of matches to display
    """
    output.print_header(username)

    # Initialize browser for authenticated API access
    output.print_progress("Initializing browser...")
    if not init_browser():
        output.print_error("Failed to initialize browser. Check ~/.substack-cookies.json")
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
            f"Scanning {len(newsletters_to_scan)} newsletters for subscribers..."
        )

        # Step 4: For each newsletter, get its subscribers
        all_candidates: Dict[int, Tuple[UserProfile, List[Newsletter]]] = {}
        newsletters_scanned = 0

        for i, newsletter in enumerate(newsletters_to_scan, 1):
            output.print_progress(
                f"  [{i}/{len(newsletters_to_scan)}] {newsletter.name} ({newsletter.subscriber_count} subs)"
            )

            # Get subscribers of this newsletter via browser
            subscribers = get_publication_subscribers_browser(
                newsletter.author_id,
                newsletter.subdomain,
                limit=subscribers_per_newsletter,
            )

            output.print_progress(f"    Found {len(subscribers)} subscribers")

            # For each subscriber, get their subscriptions
            for subscriber in subscribers:
                if input_profile and subscriber.id == input_profile.id:
                    continue  # Skip the input user

                if subscriber.id not in all_candidates:
                    if subscriber.username:
                        subscriber_subs = client.get_user_subscriptions(subscriber.username)
                        if subscriber_subs:
                            all_candidates[subscriber.id] = (subscriber, subscriber_subs)

            newsletters_scanned += 1

        output.print_progress(f"\nAnalyzing {len(all_candidates)} unique candidates...")

        # Step 5: Rank candidates by overlap
        matches = rank_matches(
            input_subs,
            list(all_candidates.values()),
            min_overlap=min_overlap,
            require_bio=require_bio,
            require_publication=require_publication,
        )

        # Step 6: Output results
        output.print_summary(
            input_username=username,
            num_subscriptions=len(input_subs),
            num_newsletters_scanned=newsletters_scanned,
            num_candidates=len(all_candidates),
            num_matches=len(matches),
        )

        output.print_matches(matches, limit=limit)

    finally:
        close_browser()


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Find friends based on Substack subscription overlap",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.main johndoe
  python -m src.main johndoe --max-newsletters 10 --require-publication
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
        default=50,
        help="Maximum subscribers to fetch per newsletter (default: 50)",
    )
    parser.add_argument(
        "--min-overlap",
        type=int,
        default=2,
        help="Minimum shared subscriptions for a match (default: 2)",
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
        )
    except KeyboardInterrupt:
        output.console.print("\n[yellow]Interrupted by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        output.print_error(str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
