"""Substack API client using raw HTTP requests."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from .cache import cache
from .types import Newsletter, UserProfile

# Rate limiting - increased to avoid 429 errors
MIN_REQUEST_INTERVAL = 4.0  # seconds between requests
_last_request_time = 0.0

BASE_URL = "https://substack.com/api/v1"

# Standard headers to mimic browser requests
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
}

# Session cookies for authenticated requests
_session_cookies: Optional[Dict[str, str]] = None


def load_cookies(cookie_path: Optional[str] = None) -> bool:
    """
    Load session cookies from file or environment variable.

    Looks for cookies in this order:
    1. Provided cookie_path
    2. SUBSTACK_COOKIES environment variable (JSON string)
    3. ~/.substack-cookies.json file

    Cookie file format (JSON):
    {
        "substack.sid": "your_session_id_here"
    }

    Returns True if cookies were loaded successfully.
    """
    global _session_cookies

    # Try provided path first
    paths_to_try = []
    if cookie_path:
        paths_to_try.append(Path(cookie_path))
    paths_to_try.append(Path.home() / ".substack-cookies.json")

    # Try environment variable
    env_cookies = os.environ.get("SUBSTACK_COOKIES")
    if env_cookies:
        try:
            _session_cookies = json.loads(env_cookies)
            return True
        except json.JSONDecodeError:
            pass

    # Try file paths
    for path in paths_to_try:
        if path.exists():
            try:
                with open(path) as f:
                    _session_cookies = json.load(f)
                return True
            except (json.JSONDecodeError, IOError):
                pass

    return False


def set_cookies(cookies: Dict[str, str]) -> None:
    """Set session cookies directly."""
    global _session_cookies
    _session_cookies = cookies


def _rate_limit() -> None:
    """Ensure we don't exceed rate limits."""
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < MIN_REQUEST_INTERVAL:
        time.sleep(MIN_REQUEST_INTERVAL - elapsed)
    _last_request_time = time.time()


def _make_request(url: str, params: Optional[dict] = None, require_auth: bool = False) -> dict:
    """Make a rate-limited GET request."""
    _rate_limit()

    cookies = _session_cookies if _session_cookies else {}

    if require_auth and not cookies:
        raise ValueError(
            "Authentication required. Set cookies via load_cookies() or set_cookies(). "
            "See ~/.substack-cookies.json or SUBSTACK_COOKIES env var."
        )

    response = requests.get(url, params=params, headers=HEADERS, cookies=cookies, timeout=30)
    response.raise_for_status()
    return response.json()


def _resolve_handle(username: str) -> str:
    """
    Resolve a username in case it was changed/redirected.

    Substack allows users to change their handle. This follows
    redirects to find the current handle.
    """
    try:
        response = requests.get(
            f"https://substack.com/@{username}",
            headers=HEADERS,
            allow_redirects=True,
            timeout=30,
        )
        # Extract handle from final URL
        final_url = str(response.url)
        if "/@" in final_url:
            return final_url.split("/@")[-1].split("?")[0].split("/")[0]
    except Exception:
        pass
    return username


def get_user_profile(username: str) -> Optional[UserProfile]:
    """Get a user's profile by username."""
    cache_key = f"profile:{username}"
    cached = cache.get(cache_key)
    if cached:
        return UserProfile(**cached)

    try:
        # Resolve handle in case it changed
        resolved_username = _resolve_handle(username)

        url = f"{BASE_URL}/user/{resolved_username}/public_profile"
        data = _make_request(url)

        profile = UserProfile(
            id=data.get("id", 0),
            username=resolved_username,
            name=data.get("name", resolved_username),
            bio=data.get("bio"),
            photo_url=data.get("photo_url"),
            has_publication=bool(data.get("primaryPublication")),
            publication_url=data.get("primaryPublication", {}).get("url") if data.get("primaryPublication") else None,
            follower_count=data.get("followerCount", 0),
        )

        # Cache the profile
        cache.set(cache_key, {
            "id": profile.id,
            "username": profile.username,
            "name": profile.name,
            "bio": profile.bio,
            "photo_url": profile.photo_url,
            "has_publication": profile.has_publication,
            "publication_url": profile.publication_url,
            "follower_count": profile.follower_count,
        })

        return profile
    except requests.exceptions.HTTPError as e:
        print(f"HTTP error fetching profile for {username}: {e}")
        return None
    except Exception as e:
        print(f"Error fetching profile for {username}: {e}")
        return None


def get_user_subscriptions(username: str) -> List[Newsletter]:
    """Get a user's subscriptions (newsletters they follow)."""
    cache_key = f"subscriptions:{username}"
    cached = cache.get(cache_key)
    if cached:
        return [Newsletter(**n) for n in cached]

    try:
        # Resolve handle in case it changed
        resolved_username = _resolve_handle(username)

        url = f"{BASE_URL}/user/{resolved_username}/public_profile"
        data = _make_request(url)

        # Subscriptions are included in the profile response
        subs_data = data.get("subscriptions", [])

        newsletters = []
        for sub in subs_data:
            # The subscription data has publication nested inside
            pub = sub.get("publication", {})
            if not pub:
                continue

            # Get author info for the author_id
            author = pub.get("author", {})
            author_id = pub.get("author_id") or pub.get("primary_user_id") or author.get("id", 0)

            newsletter = Newsletter(
                id=pub.get("id", 0),
                name=pub.get("name", "Unknown"),
                subdomain=pub.get("subdomain", ""),
                author_id=author_id,
                subscriber_count=pub.get("subscriber_count", 0),
                url=f"https://{pub.get('subdomain', '')}.substack.com" if pub.get("subdomain") else None,
            )
            newsletters.append(newsletter)

        # Cache the subscriptions
        cache.set(cache_key, [
            {
                "id": n.id,
                "name": n.name,
                "subdomain": n.subdomain,
                "author_id": n.author_id,
                "subscriber_count": n.subscriber_count,
                "url": n.url,
            }
            for n in newsletters
        ])

        return newsletters
    except requests.exceptions.HTTPError as e:
        print(f"HTTP error fetching subscriptions for {username}: {e}")
        return []
    except Exception as e:
        print(f"Error fetching subscriptions for {username}: {e}")
        return []


def get_publication_followers(user_id: int, limit: int = 100) -> List[UserProfile]:
    """
    Get followers of a publication using the subscriber-lists endpoint.

    Args:
        user_id: The numeric user ID of the publication owner
        limit: Maximum number of followers to fetch

    Returns:
        List of UserProfile objects for followers
    """
    cache_key = f"followers:{user_id}:{limit}"
    cached = cache.get(cache_key)
    if cached:
        return [UserProfile(**p) for p in cached]

    url = f"{BASE_URL}/user/{user_id}/subscriber-lists"
    params = {"lists": "followers"}

    try:
        data = _make_request(url, params, require_auth=True)

        followers = []
        follower_list = data.get("followers", [])[:limit]

        for f in follower_list:
            profile = UserProfile(
                id=f.get("id", 0),
                username=f.get("handle", f.get("username", "")),
                name=f.get("name", ""),
                bio=f.get("bio"),
                photo_url=f.get("photo_url"),
                has_publication=bool(f.get("primaryPublication")),
                publication_url=f.get("primaryPublication", {}).get("url") if f.get("primaryPublication") else None,
                follower_count=f.get("followerCount", 0),
            )
            followers.append(profile)

        # Cache the followers
        cache.set(cache_key, [
            {
                "id": p.id,
                "username": p.username,
                "name": p.name,
                "bio": p.bio,
                "photo_url": p.photo_url,
                "has_publication": p.has_publication,
                "publication_url": p.publication_url,
                "follower_count": p.follower_count,
            }
            for p in followers
        ])

        return followers
    except requests.exceptions.HTTPError as e:
        print(f"HTTP error fetching followers for user {user_id}: {e}")
        return []
    except Exception as e:
        print(f"Error fetching followers for user {user_id}: {e}")
        return []


def get_publication_posts(subdomain: str, limit: int = 5) -> List[dict]:
    """
    Get recent posts from a publication.

    Args:
        subdomain: The publication's subdomain (e.g., 'platformer')
        limit: Maximum number of posts to fetch

    Returns:
        List of post dictionaries with id, title, comment_count, etc.
    """
    cache_key = f"posts:{subdomain}:{limit}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    url = f"https://{subdomain}.substack.com/api/v1/archive"
    params = {"limit": limit}

    try:
        data = _make_request(url, params)
        posts = data if isinstance(data, list) else []
        cache.set(cache_key, posts)
        return posts
    except Exception as e:
        print(f"Error fetching posts for {subdomain}: {e}")
        return []


def get_post_commenters(subdomain: str, post_id: int, limit: int = 50) -> List[UserProfile]:
    """
    Get users who commented on a post.

    Args:
        subdomain: The publication's subdomain
        post_id: The post ID
        limit: Maximum number of commenters to return

    Returns:
        List of UserProfile objects for commenters
    """
    cache_key = f"commenters:{subdomain}:{post_id}:{limit}"
    cached = cache.get(cache_key)
    if cached:
        return [UserProfile(**p) for p in cached]

    url = f"https://{subdomain}.substack.com/api/v1/post/{post_id}/comments"
    params = {"limit": 100}  # Fetch more to get unique users

    try:
        data = _make_request(url, params)
        comments = data.get("comments", [])

        # Extract unique users from comments (including nested children)
        seen_ids: set = set()
        users: List[UserProfile] = []

        def extract_users(comment_list: list) -> None:
            for c in comment_list:
                user_id = c.get("user_id", 0)
                if user_id and user_id not in seen_ids:
                    seen_ids.add(user_id)

                    # Check if user has their own publication
                    metadata = c.get("metadata", {})
                    author_pub = metadata.get("author_on_other_pub", {})

                    profile = UserProfile(
                        id=user_id,
                        username=c.get("handle", ""),
                        name=c.get("name", ""),
                        bio=None,  # Not available in comments
                        photo_url=c.get("photo_url"),
                        has_publication=bool(author_pub),
                        publication_url=author_pub.get("base_url") if author_pub else None,
                        follower_count=0,
                    )
                    users.append(profile)

                # Process nested children
                children = c.get("children", [])
                if children:
                    extract_users(children)

        extract_users(comments)

        # Cache the results
        cache.set(cache_key, [
            {
                "id": p.id,
                "username": p.username,
                "name": p.name,
                "bio": p.bio,
                "photo_url": p.photo_url,
                "has_publication": p.has_publication,
                "publication_url": p.publication_url,
                "follower_count": p.follower_count,
            }
            for p in users[:limit]
        ])

        return users[:limit]
    except Exception as e:
        print(f"Error fetching commenters for post {post_id}: {e}")
        return []


def get_publication_subscribers(user_id: int, limit: int = 100) -> List[UserProfile]:
    """
    Get subscribers of a publication using the subscriber-lists endpoint.

    Args:
        user_id: The numeric user ID of the publication owner
        limit: Maximum number of subscribers to fetch

    Returns:
        List of UserProfile objects for subscribers
    """
    cache_key = f"subscribers:{user_id}:{limit}"
    cached = cache.get(cache_key)
    if cached:
        return [UserProfile(**p) for p in cached]

    url = f"{BASE_URL}/user/{user_id}/subscriber-lists"
    params = {"lists": "subscribers"}

    try:
        data = _make_request(url, params, require_auth=True)

        subscribers = []
        subscriber_list = data.get("subscribers", [])[:limit]

        for s in subscriber_list:
            profile = UserProfile(
                id=s.get("id", 0),
                username=s.get("handle", s.get("username", "")),
                name=s.get("name", ""),
                bio=s.get("bio"),
                photo_url=s.get("photo_url"),
                has_publication=bool(s.get("primaryPublication")),
                publication_url=s.get("primaryPublication", {}).get("url") if s.get("primaryPublication") else None,
                follower_count=s.get("followerCount", 0),
            )
            subscribers.append(profile)

        # Cache the subscribers
        cache.set(cache_key, [
            {
                "id": p.id,
                "username": p.username,
                "name": p.name,
                "bio": p.bio,
                "photo_url": p.photo_url,
                "has_publication": p.has_publication,
                "publication_url": p.publication_url,
                "follower_count": p.follower_count,
            }
            for p in subscribers
        ])

        return subscribers
    except requests.exceptions.HTTPError as e:
        print(f"HTTP error fetching subscribers for user {user_id}: {e}")
        return []
    except Exception as e:
        print(f"Error fetching subscribers for user {user_id}: {e}")
        return []
