"""
Parser module for extracting and cleaning post data from LinkedIn.
"""
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Optional, Dict
import re
from utils import normalize_text, extract_text_snippet


def parse_post_element(element, base_url: str = "https://www.linkedin.com") -> Optional[Dict]:
    """
    Parse a single LinkedIn post element and extract relevant data.
    
    Args:
        element: BeautifulSoup element or Playwright element data
        base_url: Base URL for constructing full URLs
        
    Returns:
        Dictionary with post data or None if parsing fails
    """
    try:
        # If element is a dict (from Playwright), use it directly
        if isinstance(element, dict):
            return element
        
        # If element is BeautifulSoup, parse it
        if hasattr(element, 'get'):
            # Extract post URL
            post_url_elem = element.find('a', href=re.compile(r'/posts/'))
            post_url = None
            if post_url_elem and post_url_elem.get('href'):
                href = post_url_elem.get('href')
                post_url = href if href.startswith('http') else base_url + href
            
            # Extract author info
            author_elem = element.find('a', href=re.compile(r'/in/'))
            author_url = None
            author_name = None
            if author_elem:
                href = author_elem.get('href', '')
                author_url = href if href.startswith('http') else base_url + href
                author_name = normalize_text(author_elem.get_text())
            
            # Extract post text
            text_elem = element.find('div', class_=re.compile(r'feed-shared-update-v2__description'))
            if not text_elem:
                text_elem = element.find('span', {'dir': 'ltr'})
            if not text_elem:
                text_elem = element.find('div', class_=re.compile(r'text'))
            
            text = ""
            if text_elem:
                text = normalize_text(text_elem.get_text())
            
            # Extract date
            date_elem = element.find('time')
            date_posted = None
            if date_elem:
                datetime_attr = date_elem.get('datetime')
                if datetime_attr:
                    try:
                        date_posted = datetime.fromisoformat(datetime_attr.replace('Z', '+00:00'))
                    except:
                        pass
                else:
                    date_text = date_elem.get_text()
                    date_posted = parse_relative_date(date_text)
            
            # Extract engagement metrics (optional)
            likes = extract_engagement(element, 'like')
            comments = extract_engagement(element, 'comment')
            
            if not post_url or not text:
                return None
            
            return {
                'post_url': post_url,
                'author_url': author_url or '',
                'author_name': author_name or 'Unknown',
                'text': text,
                'text_snippet': extract_text_snippet(text),
                'date_posted': date_posted or datetime.now(),
                'likes': likes,
                'comments': comments
            }
    
    except Exception as e:
        print(f"Error parsing post element: {e}")
        return None
    
    return None


def parse_relative_date(date_text: str) -> Optional[datetime]:
    """
    Parse relative date strings like "2 hours ago", "3 days ago".
    
    Args:
        date_text: Relative date string
        
    Returns:
        Datetime object or None if parsing fails
    """
    if not date_text:
        return None
    
    date_text = date_text.lower().strip()
    now = datetime.now()
    
    # Match patterns like "2 hours ago", "3 days ago"
    patterns = [
        (r'(\d+)\s*hour', lambda x: now.replace(hour=now.hour - int(x))),
        (r'(\d+)\s*day', lambda x: now.replace(day=now.day - int(x))),
        (r'(\d+)\s*week', lambda x: now.replace(day=now.day - int(x) * 7)),
        (r'(\d+)\s*month', lambda x: now.replace(month=now.month - int(x))),
    ]
    
    for pattern, func in patterns:
        match = re.search(pattern, date_text)
        if match:
            try:
                return func(match.group(1))
            except:
                pass
    
    return now


def extract_engagement(element, metric_type: str) -> int:
    """
    Extract engagement metrics (likes, comments) from post element.
    
    Args:
        element: BeautifulSoup element
        metric_type: 'like' or 'comment'
        
    Returns:
        Number of engagements (0 if not found)
    """
    try:
        # Look for engagement indicators
        pattern = re.compile(f'.*{metric_type}.*', re.I)
        engagement_elem = element.find(string=pattern)
        
        if engagement_elem:
            # Extract number from text like "5 likes" or "12 comments"
            numbers = re.findall(r'\d+', engagement_elem)
            if numbers:
                return int(numbers[0])
    except:
        pass
    
    return 0


def clean_post_data(post: Dict) -> Dict:
    """
    Clean and normalize post data.
    
    Args:
        post: Raw post dictionary
        
    Returns:
        Cleaned post dictionary
    """
    cleaned = post.copy()
    
    # Normalize text fields
    if 'text' in cleaned:
        cleaned['text'] = normalize_text(cleaned['text'])
        cleaned['text_snippet'] = extract_text_snippet(cleaned['text'])
    
    # Ensure URLs are complete
    if 'post_url' in cleaned and cleaned['post_url']:
        if not cleaned['post_url'].startswith('http'):
            cleaned['post_url'] = 'https://www.linkedin.com' + cleaned['post_url']
    
    if 'author_url' in cleaned and cleaned['author_url']:
        if not cleaned['author_url'].startswith('http'):
            cleaned['author_url'] = 'https://www.linkedin.com' + cleaned['author_url']
    
    # Ensure date is datetime object
    if 'date_posted' in cleaned:
        if isinstance(cleaned['date_posted'], str):
            try:
                cleaned['date_posted'] = datetime.fromisoformat(cleaned['date_posted'])
            except:
                cleaned['date_posted'] = datetime.now()
    
    return cleaned

