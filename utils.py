"""
Utility functions for hashing, keyword matching, and text processing.
"""
import hashlib
import re
from typing import List, Set


def hash_url(url: str) -> str:
    """
    Generate a hash for a URL to use as a unique identifier.
    
    Args:
        url: The URL to hash
        
    Returns:
        A hexadecimal hash string
    """
    return hashlib.md5(url.encode()).hexdigest()


def calculate_relevance_score(text: str, keywords: List[str]) -> int:
    """
    Calculate relevance score based on keyword matches in text.
    
    Args:
        text: The post text to score
        keywords: List of keywords to match
        
    Returns:
        Score (number of keyword matches found)
    """
    if not text or not keywords:
        return 0
    
    text_lower = text.lower()
    score = 0
    
    for keyword in keywords:
        # Case-insensitive word boundary matching
        pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
        matches = len(re.findall(pattern, text_lower))
        score += matches
    
    return score


def normalize_text(text: str) -> str:
    """
    Normalize text by removing extra whitespace and newlines.
    
    Args:
        text: Raw text to normalize
        
    Returns:
        Cleaned text string
    """
    if not text:
        return ""
    
    # Remove extra whitespace and newlines
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    
    return text


def extract_text_snippet(text: str, max_length: int = 200) -> str:
    """
    Extract a snippet of text for display purposes.
    
    Args:
        text: Full text
        max_length: Maximum length of snippet
        
    Returns:
        Truncated text with ellipsis if needed
    """
    if not text:
        return ""
    
    if len(text) <= max_length:
        return text
    
    # Try to cut at word boundary
    snippet = text[:max_length]
    last_space = snippet.rfind(' ')
    
    if last_space > max_length * 0.8:  # If we found a space reasonably close
        snippet = snippet[:last_space]
    
    return snippet + "..."


def deduplicate_posts(posts: List[dict], key: str = "post_url") -> List[dict]:
    """
    Remove duplicate posts based on a key field.
    
    Args:
        posts: List of post dictionaries
        key: Field name to use for deduplication
        
    Returns:
        List of unique posts (first occurrence kept)
    """
    seen = set()
    unique_posts = []
    
    for post in posts:
        post_key = post.get(key)
        # If post_url is empty, use text hash as fallback
        if not post_key and key == "post_url":
            text = post.get('text', '')
            if text:
                import hashlib
                post_key = hashlib.md5(text.encode()).hexdigest()
        
        # If still no key, use text snippet
        if not post_key:
            text = post.get('text', '')[:50]
            if text:
                import hashlib
                post_key = hashlib.md5(text.encode()).hexdigest()
        
        if post_key and post_key not in seen:
            seen.add(post_key)
            unique_posts.append(post)
        elif not post_key:
            # If no key at all, still include the post (might be first one)
            unique_posts.append(post)
    
    return unique_posts

