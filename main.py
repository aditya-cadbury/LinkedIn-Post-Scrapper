"""
Main entry point for LinkedIn Hiring Post Scraper.
"""
import json
import os
import sys
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict
from scraper import LinkedInScraper
from storage import StorageManager, write_log
from utils import calculate_relevance_score, deduplicate_posts
from parser import clean_post_data


def load_config(config_file: str = "config.json") -> dict:
    """
    Load configuration from JSON file.
    
    Args:
        config_file: Path to configuration file
        
    Returns:
        Configuration dictionary
    """
    if not os.path.exists(config_file):
        print(f"Error: Config file '{config_file}' not found.")
        sys.exit(1)
    
    with open(config_file, 'r') as f:
        return json.load(f)


def filter_posts_by_date(posts: List[Dict], days_limit: int) -> List[Dict]:
    """
    Filter posts by date (only keep posts within days_limit).
    
    Args:
        posts: List of post dictionaries
        days_limit: Maximum number of days ago to include
        
    Returns:
        Filtered list of posts
    """
    if not days_limit or days_limit <= 0:
        return posts
    
    cutoff_date = datetime.now() - timedelta(days=days_limit)
    filtered = []
    
    for post in posts:
        date_posted = post.get('date_posted')
        if isinstance(date_posted, datetime):
            if date_posted >= cutoff_date:
                filtered.append(post)
        elif isinstance(date_posted, str):
            try:
                date_obj = datetime.fromisoformat(date_posted.replace('Z', '+00:00'))
                if date_obj >= cutoff_date:
                    filtered.append(post)
            except:
                # If date parsing fails, include the post
                filtered.append(post)
        else:
            # If no date, include the post
            filtered.append(post)
    
    return filtered


def score_and_rank_posts(posts: List[Dict], keywords: List[str]) -> List[Dict]:
    """
    Calculate relevance scores and rank posts.
    
    Args:
        posts: List of post dictionaries
        keywords: List of keywords for scoring
        
    Returns:
        List of posts with scores, sorted by score (descending)
    """
    for post in posts:
        text = post.get('text', '')
        score = calculate_relevance_score(text, keywords)
        post['score'] = score
    
    # Sort by score descending
    posts.sort(key=lambda x: x.get('score', 0), reverse=True)
    
    return posts


def print_top_posts(posts: List[Dict], limit: int = 5):
    """
    Print top posts to console in a formatted table.
    
    Args:
        posts: List of post dictionaries
        limit: Number of top posts to display
    """
    if not posts:
        print("No posts to display.")
        return
    
    top_posts = posts[:limit]
    
    print("\n" + "="*100)
    print(f"TOP {len(top_posts)} HIRING POSTS (by relevance score)")
    print("="*100)
    print(f"{'Date':<12} {'Author':<25} {'Score':<6} {'Text Snippet':<50}")
    print("-"*100)
    
    for post in top_posts:
        date = post.get('date_posted', '')
        if isinstance(date, datetime):
            date_str = date.strftime('%Y-%m-%d')
        else:
            date_str = str(date)[:10]
        
        author = post.get('author_name', 'Unknown')[:24]
        score = post.get('score', 0)
        snippet = post.get('text_snippet', '')[:48]
        
        print(f"{date_str:<12} {author:<25} {score:<6} {snippet:<50}")
        print(f"{'':12} {'URL: ' + post.get('post_url', '')[:80]}")
        print("-"*100)


async def main():
    """Main execution function."""
    print("="*100)
    print("LinkedIn Hiring Post Scraper")
    print("="*100)
    
    # Load configuration
    config = load_config()
    keywords = config.get('keywords', [])
    hashtags = config.get('hashtags', [])
    days_limit = config.get('days_limit', 7)
    
    # Get scraping config
    scraping_config = config.get('scraping', {})
    headless = scraping_config.get('headless', False)
    delay = scraping_config.get('delay_between_requests', 2)
    max_posts = scraping_config.get('max_posts_per_search', 50)
    timeout = scraping_config.get('timeout', 30000)
    
    print(f"\n{'='*100}")
    print(f"CONFIGURATION LOADED:")
    print(f"{'='*100}")
    print(f"  Keywords ({len(keywords)}): {', '.join(keywords[:5])}{'...' if len(keywords) > 5 else ''}")
    print(f"  Hashtags ({len(hashtags)}): {', '.join(hashtags[:3])}{'...' if len(hashtags) > 3 else ''}")
    print(f"  Days limit: {days_limit} days")
    print(f"  Headless mode: {headless}")
    print(f"  Delay between requests: {delay} seconds")
    print(f"  Max posts per search: {max_posts}")
    print(f"  Timeout: {timeout}ms")
    print(f"{'='*100}\n")
    
    # Initialize scraper
    scraper = LinkedInScraper(config)
    
    try:
        # Scrape LinkedIn posts
        print("Starting LinkedIn scraping...")
        posts = await scraper.scrape(keywords, hashtags)
        
        if not posts:
            print("WARNING: No posts found. Make sure you're logged in (cookies.json exists).")
            # Still show where data would be saved
            import os
            csv_path = os.path.abspath(config.get('storage', {}).get('csv_file', 'output.csv'))
            db_path = os.path.abspath(config.get('storage', {}).get('db_file', 'output.db'))
            print(f"\nData would be saved to:")
            print(f"   CSV File: {csv_path}")
            print(f"   SQLite Database: {db_path}")
            return
        
        print(f"Found {len(posts)} posts")
        
        # Filter by date
        if days_limit > 0:
            posts = filter_posts_by_date(posts, days_limit)
            print(f"After date filter ({days_limit} days): {len(posts)} posts")
        
        # Remove duplicates
        print(f"Before deduplication: {len(posts)} posts")
        posts = deduplicate_posts(posts, key='post_url')
        print(f"After deduplication: {len(posts)} posts")
        
        if not posts:
            print("WARNING: All posts were removed during deduplication.")
            print("   This might indicate missing post_urls. Checking...")
            # Don't re-scrape, just show where data would be saved
        
        # Score and rank posts
        posts = score_and_rank_posts(posts, keywords)
        print(f"Posts scored and ranked by relevance")
        
        # Clean post data
        posts = [clean_post_data(post) for post in posts]
        
        # Save to storage (even if empty, show where it would be saved)
        import os
        csv_file = config.get('storage', {}).get('csv_file', 'output.csv')
        db_file = config.get('storage', {}).get('db_file', 'output.db')
        csv_path = os.path.abspath(csv_file)
        db_path = os.path.abspath(db_file)
        
        if posts:
            storage = StorageManager(csv_file=csv_file, db_file=db_file)
            storage.save_posts(posts)
            print(f"\nSaved {len(posts)} posts to storage")
        else:
            print(f"\nWARNING: No posts to save (all removed during processing)")
            print(f"   Data would be saved to:")
            print(f"   CSV: {csv_path}")
            print(f"   DB: {db_path}")
        
        # Write log
        log_file = config.get('storage', {}).get('log_file', 'logs/last_run.txt')
        write_log(log_file, f"Scraped {len(posts)} posts. Top score: {posts[0].get('score', 0) if posts else 0}")
        
        # Print top posts
        print_top_posts(posts, limit=5)
        
        # Get absolute paths for clarity
        import os
        csv_path = os.path.abspath(config.get('storage', {}).get('csv_file', 'output.csv'))
        db_path = os.path.abspath(config.get('storage', {}).get('db_file', 'output.db'))
        log_path = os.path.abspath(log_file)
        
        print(f"\n{'='*100}")
        print(f"SCRAPING COMPLETE!")
        print(f"{'='*100}")
        print(f"\nSCRAPED DATA SAVED TO:")
        print(f"   CSV File: {csv_path}")
        print(f"   SQLite Database: {db_path}")
        print(f"   Log File: {log_path}")
        print(f"\nYou can:")
        print(f"   - Open {csv_path} in Excel/Google Sheets to view the data")
        print(f"   - Query {db_path} using SQLite tools")
        print(f"   - Check {log_path} for execution logs")
        print(f"\nSummary:")
        print(f"   - Total posts scraped: {len(posts)}")
        print(f"   - Top relevance score: {posts[0].get('score', 0) if posts else 0}")
        print(f"   - Posts with hiring keywords: {sum(1 for p in posts if p.get('score', 0) > 0)}")
        print(f"{'='*100}")
    
    except KeyboardInterrupt:
        print("\n\nScraping interrupted by user.")
        print("Your login session is saved. Browser will stay open.")
    except Exception as e:
        print(f"\nERROR: Error during scraping: {e}")
        import traceback
        traceback.print_exc()
        print("\nYour login session is saved. Browser will stay open.")
    finally:
        # Don't close browser - let user close manually to preserve session
        print("\nTip: Keep the browser window open to preserve your login session.")
        print("   Close it manually when you're done.")
        # await scraper.close()  # Commented out to preserve session


if __name__ == "__main__":
    # Run async main function
    asyncio.run(main())

