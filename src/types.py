"""Type definitions for Substack Friend Finder."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class UserProfile:
    """A Substack user profile."""
    id: int
    username: str
    name: str
    bio: Optional[str] = None
    photo_url: Optional[str] = None
    has_publication: bool = False
    publication_url: Optional[str] = None
    follower_count: int = 0


@dataclass
class Newsletter:
    """A Substack newsletter/publication."""
    id: int
    name: str
    subdomain: str
    author_id: int
    subscriber_count: int = 0
    url: Optional[str] = None


@dataclass
class Match:
    """A matched user with overlap score."""
    user: UserProfile
    score: float
    shared_newsletters: List[Newsletter] = field(default_factory=list)

    def __lt__(self, other: "Match") -> bool:
        """Sort by score descending."""
        return self.score > other.score
