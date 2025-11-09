"""
Scraper module using Playwright to extract LinkedIn posts.
"""
import asyncio
import json
import os
from datetime import datetime
from typing import List, Dict, Optional
from playwright.async_api import async_playwright, Browser, Page, TimeoutError as PlaywrightTimeoutError
from parser import clean_post_data
from storage import StorageManager


class LinkedInScraper:
    """
    LinkedIn scraper using Playwright for dynamic content rendering.
    """
    
    def __init__(self, config: dict, cookies_file: Optional[str] = None):
        """
        Initialize LinkedIn scraper.
        
        Args:
            config: Configuration dictionary
            cookies_file: Optional path to cookies JSON file for authentication
        """
        self.config = config
        self.cookies_file = cookies_file or "cookies.json"
        self.browser: Optional[Browser] = None
        self.context = None
        self.page: Optional[Page] = None
        self.playwright = None
        self.storage = StorageManager(
            csv_file=config.get('storage', {}).get('csv_file', 'output.csv'),
            db_file=config.get('storage', {}).get('db_file', 'output.db')
        )
    
    async def start_browser(self):
        """Start Playwright browser with persistent user data to save login session."""
        self.playwright = await async_playwright().start()
        browser_config = self.config.get('scraping', {})
        headless = browser_config.get('headless', False)
        self.timeout = browser_config.get('timeout', 30000)  # Store timeout for use throughout
        
        # Use persistent user data directory to save login session
        user_data_dir = os.path.join(os.path.expanduser('~'), '.linkedin_scraper_browser')
        os.makedirs(user_data_dir, exist_ok=True)
        
        print(f"Using persistent browser data directory: {user_data_dir}")
        print("This will save your LinkedIn login session between runs.")
        
        # Launch browser with persistent user data directory
        try:
            self.browser = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=headless,
                viewport={"width": 1920, "height": 1080},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='en-US',
                extra_http_headers={
                    'Accept-Language': 'en-US,en;q=0.9',
                },
                args=[
                    '--disable-blink-features=AutomationControlled',
                ]
            )
            # With persistent context, browser is the context
            self.context = self.browser
            
            # Get existing page or create new one
            if len(self.context.pages) > 0:
                self.page = self.context.pages[0]
            else:
                self.page = await self.context.new_page()
            
            # Add script to hide webdriver property
            try:
                await self.context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                """)
            except Exception as e:
                print(f"Warning: Could not add init script: {e}")
                
        except Exception as e:
            print(f"Error launching persistent browser: {e}")
            print("Falling back to regular browser launch...")
            # Fallback to regular browser if persistent context fails
            try:
                self.browser = await self.playwright.chromium.launch(
                    headless=headless,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                    ]
                )
                self.context = await self.browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                )
                self.page = await self.context.new_page()
            except Exception as fallback_error:
                print(f"Error with fallback browser: {fallback_error}")
                raise
        
        # Load and add cookies if available
        if os.path.exists(self.cookies_file):
            try:
                with open(self.cookies_file, 'r') as f:
                    cookies = json.load(f)
                    
                    # Normalize cookie format for Playwright
                    normalized_cookies = []
                    for cookie in cookies:
                        normalized_cookie = cookie.copy()
                        
                        # Normalize sameSite value (Playwright expects Strict|Lax|None)
                        if 'sameSite' in normalized_cookie:
                            same_site = normalized_cookie['sameSite']
                            if isinstance(same_site, str):
                                same_site_lower = same_site.lower()
                                if same_site_lower == 'none':
                                    normalized_cookie['sameSite'] = 'None'
                                elif same_site_lower == 'strict':
                                    normalized_cookie['sameSite'] = 'Strict'
                                elif same_site_lower == 'lax':
                                    normalized_cookie['sameSite'] = 'Lax'
                                else:
                                    # Default to Lax if invalid
                                    normalized_cookie['sameSite'] = 'Lax'
                            else:
                                normalized_cookie['sameSite'] = 'Lax'
                        else:
                            # Default to Lax if not specified
                            normalized_cookie['sameSite'] = 'Lax'
                        
                        # Ensure required fields
                        if 'domain' not in normalized_cookie:
                            normalized_cookie['domain'] = '.linkedin.com'
                        if 'path' not in normalized_cookie:
                            normalized_cookie['path'] = '/'
                        
                        normalized_cookies.append(normalized_cookie)
                    
                    # Navigate to LinkedIn first (required before adding cookies)
                    try:
                        # Check if page is still valid before navigation
                        if self.page.is_closed():
                            print("Page was closed, recreating...")
                            self.page = await self.context.new_page()
                        
                        timeout = self.config.get('scraping', {}).get('timeout', 30000)
                        await self.page.goto("https://www.linkedin.com", wait_until="domcontentloaded", timeout=timeout)
                        await asyncio.sleep(2)  # Give it more time
                        
                        # Check if page is still valid after navigation
                        if self.page.is_closed():
                            print("Page was closed after navigation, recreating...")
                            self.page = await self.context.new_page()
                            timeout = self.config.get('scraping', {}).get('timeout', 30000)
                            await self.page.goto("https://www.linkedin.com", wait_until="domcontentloaded", timeout=timeout)
                            await asyncio.sleep(1)
                        
                        # Add cookies to context
                        try:
                            await self.context.add_cookies(normalized_cookies)
                            print(f"Loaded {len(normalized_cookies)} cookies from {self.cookies_file}")
                        except Exception as cookie_error:
                            print(f"Warning: Could not add cookies: {cookie_error}")
                    except Exception as nav_error:
                        print(f"Warning: Navigation error: {nav_error}")
                        # Check if we need to recreate the page
                        if self.page.is_closed() or 'TargetClosedError' in str(type(nav_error)):
                            print("Recreating page after error...")
                            try:
                                self.page = await self.context.new_page()
                                timeout = self.config.get('scraping', {}).get('timeout', 30000)
                                await self.page.goto("https://www.linkedin.com", wait_until="domcontentloaded", timeout=timeout)
                                await asyncio.sleep(1)
                                # Try to add cookies
                                await self.context.add_cookies(normalized_cookies)
                                print(f"Loaded {len(normalized_cookies)} cookies from {self.cookies_file}")
                            except Exception as retry_error:
                                print(f"Warning: Could not recover from navigation error: {retry_error}")
            except Exception as e:
                print(f"Warning: Could not load cookies: {e}")
                import traceback
                traceback.print_exc()
        else:
            # No cookies, just navigate to LinkedIn
            try:
                if self.page.is_closed():
                    self.page = await self.context.new_page()
                await self.page.goto("https://www.linkedin.com", wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(1)
            except Exception as e:
                print(f"Warning: Could not navigate to LinkedIn: {e}")
                # Try to recreate page
                if self.page.is_closed() or 'TargetClosedError' in str(type(e)):
                    try:
                        self.page = await self.context.new_page()
                        timeout = self.config.get('scraping', {}).get('timeout', 30000)
                        await self.page.goto("https://www.linkedin.com", wait_until="domcontentloaded", timeout=timeout)
                    except Exception as retry_error:
                        print(f"Warning: Could not recover: {retry_error}")
    
    async def login(self, email: Optional[str] = None, password: Optional[str] = None):
        """
        Login to LinkedIn (if cookies not available).
        Goes directly to login page without checking feed first.
        
        Args:
            email: LinkedIn email (optional if using cookies)
            password: LinkedIn password (optional if using cookies)
        """
        if not self.page:
            await self.start_browser()
        
        # Go directly to login page (faster than checking feed)
        timeout = self.config.get('scraping', {}).get('timeout', 30000)
        print("Navigating to login page...")
        try:
            await self.page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded", timeout=timeout)
            await asyncio.sleep(1)  # Minimal wait
            
            # Check if we got redirected (means already logged in)
            current_url = self.page.url.lower()
            if "feed" in current_url or ("linkedin.com" in current_url and "login" not in current_url):
                print("Already logged in (redirected from login page)")
                return
        except Exception as e:
            print(f"Warning: Could not navigate to login page: {e}")
            # Try to check current URL
            try:
                current_url = self.page.url.lower()
                if "feed" in current_url:
                    print("Already logged in")
                    return
            except:
                pass
        
        # If not logged in and credentials provided, attempt login
        if email and password:
            print("Attempting to login with credentials...")
            try:
                # Make sure we're on login page
                if "login" not in self.page.url.lower():
                    await self.page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded", timeout=timeout)
                    await asyncio.sleep(1)
                
                await self.page.fill('input[name="session_key"]', email)
                await self.page.fill('input[name="session_password"]', password)
                await self.page.click('button[type="submit"]')
                
                # Wait for navigation (use commit for faster response)
                await self.page.wait_for_load_state("domcontentloaded", timeout=timeout)
                await asyncio.sleep(2)  # Reduced from 3
                
                # Save cookies after successful login
                cookies = await self.page.context.cookies()
                with open(self.cookies_file, 'w') as f:
                    json.dump(cookies, f, indent=2)
                print("Login successful, cookies saved")
            except Exception as e:
                print(f"ERROR: Login failed: {e}")
                raise
        else:
            print("WARNING: No credentials provided. Please login manually in the browser or provide cookies.json")
    
    async def search_posts(self, keywords: List[str], hashtags: List[str] = None, max_posts: int = None) -> List[Dict]:
        """
        Search for LinkedIn posts using keywords and hashtags.
        Searches both the feed and search results.
        
        Args:
            keywords: List of keywords to search for
            hashtags: List of hashtags to search for
            max_posts: Maximum number of posts to retrieve
            
        Returns:
            List of post dictionaries
        """
        if not self.page:
            await self.start_browser()
        
        all_posts = []
        hashtags = hashtags or []
        
        # Get max_posts from config if not provided
        if max_posts is None:
            max_posts = self.config.get('scraping', {}).get('max_posts_per_search', 50)
        
        # Combine keywords and hashtags for search
        search_terms = keywords + hashtags
        
        # Avoid division by zero
        if not search_terms:
            print("No search terms provided")
            return []
        
        print(f"\nSearching for posts with {len(keywords)} keywords and {len(hashtags)} hashtags...")
        print(f"   Keywords: {', '.join(keywords)}")
        if hashtags:
            print(f"   Hashtags: {', '.join(hashtags)}")
        
        # Method 1: Search the feed for posts containing keywords
        try:
            print("\nMethod 1: Searching LinkedIn feed...")
            timeout = self.config.get('scraping', {}).get('timeout', 30000)
            try:
                await self.page.goto("https://www.linkedin.com/feed/", wait_until="commit", timeout=timeout)
                await asyncio.sleep(5)  # Wait for feed to load
            except Exception as nav_error:
                print(f"   WARNING: Navigation error: {nav_error}")
                await asyncio.sleep(5)
                # Check if we're already on the feed
                try:
                    current_url = self.page.url.lower()
                    if "feed" not in current_url:
                        print("   Trying to navigate again...")
                        timeout = self.config.get('scraping', {}).get('timeout', 30000)
                        await self.page.goto("https://www.linkedin.com/feed/", wait_until="commit", timeout=timeout)
                        await asyncio.sleep(5)
                except Exception:
                    pass
            
            await asyncio.sleep(3)
            
            # Check if page is still valid
            try:
                if self.page.is_closed():
                    print("   WARNING: Page was closed, getting new page...")
                    if self.context and len(self.context.pages) > 0:
                        self.page = self.context.pages[0]
                    else:
                        self.page = await self.context.new_page()
            except Exception:
                pass
            
            # Scroll to load more posts
            print("   Scrolling to load posts...")
            try:
                await self._scroll_and_load_posts(5)  # Scroll 5 times
            except Exception as scroll_error:
                print(f"   WARNING: Error scrolling: {scroll_error}")
            
            # Extract posts from feed
            feed_posts = await self._extract_posts_from_page()
            print(f"   Found {len(feed_posts)} posts in feed")
            all_posts.extend(feed_posts)
        except Exception as e:
            print(f"   WARNING: Error searching feed: {e}")
            import traceback
            traceback.print_exc()
        
        # Method 2: Search using LinkedIn search for each keyword/hashtag
        print(f"\nMethod 2: Searching LinkedIn for {len(search_terms)} terms...")
        for i, term in enumerate(search_terms, 1):
            try:
                print(f"\n   [{i}/{len(search_terms)}] Searching for '{term}'...")
                
                # Check if page is still valid
                try:
                    if self.page.is_closed():
                        print(f"   ⚠️  Page was closed, getting new page...")
                        if self.context and len(self.context.pages) > 0:
                            self.page = self.context.pages[0]
                        else:
                            self.page = await self.context.new_page()
                except Exception:
                    pass
                
                # Navigate to LinkedIn search
                search_url = f"https://www.linkedin.com/search/results/content/?keywords={term.replace('#', '%23')}"
                timeout = self.config.get('scraping', {}).get('timeout', 30000)
                try:
                    await self.page.goto(search_url, wait_until="commit", timeout=timeout)
                    await asyncio.sleep(3)  # Wait for search results to load
                except Exception as nav_error:
                    print(f"   WARNING: Navigation error: {nav_error}")
                    try:
                        await self.page.goto(search_url, wait_until="commit", timeout=timeout)
                        await asyncio.sleep(3)
                    except Exception:
                        print(f"   WARNING: Could not navigate to search page for '{term}', skipping...")
                        continue
                
                await asyncio.sleep(3)
                
                # Scroll to load more posts
                print(f"   Scrolling to load posts for '{term}'...")
                try:
                    await self._scroll_and_load_posts(3)
                except Exception as scroll_error:
                    print(f"   WARNING: Error scrolling: {scroll_error}")
                
                # Extract posts from current page
                posts = await self._extract_posts_from_page()
                print(f"   Found {len(posts)} posts for '{term}'")
                all_posts.extend(posts)
                
                # Add delay between requests (from config)
                delay = self.config.get('scraping', {}).get('delay_between_requests', 2)
                print(f"   Waiting {delay} seconds before next search...")
                await asyncio.sleep(delay)
                
            except Exception as e:
                print(f"   WARNING: Error searching for '{term}': {e}")
                import traceback
                traceback.print_exc()
                continue
        
        print(f"\nTotal posts found: {len(all_posts)}")
        
        # Debug: Check post_urls before deduplication
        posts_with_url = sum(1 for p in all_posts if p.get('post_url'))
        posts_without_url = len(all_posts) - posts_with_url
        if posts_without_url > 0:
            print(f"   WARNING: {posts_without_url} posts missing post_url (will use text hash for deduplication)")
        
        # Remove duplicates
        try:
            from utils import deduplicate_posts
            unique_posts = deduplicate_posts(all_posts, key='post_url')
            print(f"   After deduplication: {len(unique_posts)} unique posts")
        except ImportError:
            # Fallback if utils module not available
            import hashlib
            seen_urls = set()
            unique_posts = []
            for post in all_posts:
                post_url = post.get('post_url')
                # If no post_url, use text hash
                if not post_url:
                    text = post.get('text', '')
                    if text:
                        post_url = hashlib.md5(text.encode()).hexdigest()
                    else:
                        post_url = f"post_{len(unique_posts)}"
                
                if post_url not in seen_urls:
                    seen_urls.add(post_url)
                    unique_posts.append(post)
        
        # Apply max_total_posts limit if configured (optional safety limit)
        max_total = self.config.get('scraping', {}).get('max_total_posts')
        if max_total and len(unique_posts) > max_total:
            print(f"   WARNING: Limiting to {max_total} posts (max_total_posts setting)")
            unique_posts = unique_posts[:max_total]
        else:
            print(f"   Returning {len(unique_posts)} unique posts")
        
        return unique_posts
    
    async def _scroll_and_load_posts(self, target_count: int):
        """Scroll page to load more posts dynamically."""
        try:
            scroll_pause = 1
            # Check if page is still valid
            if self.page.is_closed():
                return
            
            last_height = await self.page.evaluate("document.body.scrollHeight")
            scroll_count = 0
            max_scrolls = target_count if target_count > 0 else 10
            
            while scroll_count < max_scrolls:
                # Check if page is still valid before scrolling
                try:
                    if self.page.is_closed():
                        break
                    
                    # Scroll down
                    await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await asyncio.sleep(scroll_pause)
                    
                    # Check if new content loaded
                    new_height = await self.page.evaluate("document.body.scrollHeight")
                    if new_height == last_height:
                        break
                    
                    last_height = new_height
                    scroll_count += 1
                except Exception as scroll_error:
                    # If page closed or error, stop scrolling
                    break
        except Exception as e:
            print(f"   WARNING: Error in scroll function: {e}")
    
    async def _extract_posts_from_page(self) -> List[Dict]:
        """Extract post data from the current page."""
        posts = []
        
        try:
            # Wait a bit for page to load
            await asyncio.sleep(2)
            
            # Try multiple selectors for LinkedIn posts
            post_selectors = [
                'div[data-id*="urn:li:activity"]',
                'div.feed-shared-update-v2',
                'article.feed-shared-update-v2',
                'div[data-urn*="urn:li:activity"]',
                'div.update-components-actor',
            ]
            
            post_elements = []
            for selector in post_selectors:
                try:
                    await self.page.wait_for_selector(selector, timeout=5000)
                    elements = await self.page.query_selector_all(selector)
                    if elements:
                        print(f"Found {len(elements)} posts using selector: {selector}")
                        post_elements = elements
                        break
                except Exception:
                    continue
            
            if not post_elements:
                print("WARNING: No posts found with any selector. Trying to find any post-like elements...")
                # Try to find any divs that might be posts
                all_divs = await self.page.query_selector_all('div')
                print(f"Found {len(all_divs)} divs on page")
                # Look for divs with specific classes or attributes
                for div in all_divs[:50]:  # Check first 50 divs
                    try:
                        class_name = await div.get_attribute('class')
                        if class_name and ('feed' in class_name.lower() or 'update' in class_name.lower() or 'post' in class_name.lower()):
                            post_elements.append(div)
                    except Exception:
                        continue
                print(f"Found {len(post_elements)} potential post elements")
            
            for element in post_elements[:20]:  # Limit to first 20 posts per page
                try:
                    post_data = await self._extract_single_post(element)
                    if post_data:
                        posts.append(post_data)
                        print(f"  Extracted post: {post_data.get('author_name', 'Unknown')} - {post_data.get('text_snippet', '')[:50]}...")
                except Exception as e:
                    # Don't print every error, just continue
                    continue
        
        except PlaywrightTimeoutError:
            print("WARNING: Timeout waiting for posts to load")
        except Exception as e:
            print(f"WARNING: Error extracting posts: {e}")
        
        return posts
    
    async def _extract_single_post(self, element) -> Optional[Dict]:
        """Extract data from a single post element."""
        try:
            # Extract post URL
            post_link = await element.query_selector('a[href*="/posts/"]')
            post_url = None
            if post_link:
                href = await post_link.get_attribute('href')
                if href:
                    post_url = href if href.startswith('http') else f"https://www.linkedin.com{href}"
            
            # Extract author info
            author_link = await element.query_selector('a[href*="/in/"]')
            author_url = None
            author_name = None
            if author_link:
                href = await author_link.get_attribute('href')
                if href:
                    author_url = href if href.startswith('http') else f"https://www.linkedin.com{href}"
                    author_name = await author_link.inner_text()
                    author_name = author_name.strip() if author_name else None
            
            # Extract post text
            text_selectors = [
                'div.feed-shared-update-v2__description',
                'span[dir="ltr"]',
                'div.feed-shared-text-view'
            ]
            
            text = ""
            for selector in text_selectors:
                text_elem = await element.query_selector(selector)
                if text_elem:
                    text = await text_elem.inner_text()
                    if text:
                        break
            
            # Extract date
            time_elem = await element.query_selector('time')
            date_posted = None
            if time_elem:
                datetime_attr = await time_elem.get_attribute('datetime')
                if datetime_attr:
                    try:
                        date_posted = datetime.fromisoformat(datetime_attr.replace('Z', '+00:00'))
                    except (ValueError, AttributeError):
                        pass
                
                # Fallback to relative date parsing
                if not date_posted:
                    date_text = await time_elem.inner_text()
                    if date_text:
                        try:
                            from parser import parse_relative_date
                            date_posted = parse_relative_date(date_text)
                        except ImportError:
                            pass
            
            # Extract engagement metrics
            likes = 0
            comments = 0
            
            # Try to find likes
            likes_elem = await element.query_selector('button[aria-label*="like"], span[class*="reactions"]')
            if likes_elem:
                likes_text = await likes_elem.inner_text()
                if likes_text:
                    import re
                    numbers = re.findall(r'\d+', likes_text.replace(',', ''))
                    if numbers:
                        likes = int(numbers[0])
            
            # Try to find comments
            comments_elem = await element.query_selector('button[aria-label*="comment"], span[class*="comments"]')
            if comments_elem:
                comments_text = await comments_elem.inner_text()
                if comments_text:
                    import re
                    numbers = re.findall(r'\d+', comments_text.replace(',', ''))
                    if numbers:
                        comments = int(numbers[0])
            
            # If we don't have post_url, try to construct it from other data
            if not post_url:
                # Try to find any link in the post
                any_link = await element.query_selector('a[href]')
                if any_link:
                    href = await any_link.get_attribute('href')
                    if href and '/posts/' in href:
                        post_url = href if href.startswith('http') else f"https://www.linkedin.com{href}"
            
            # If we still don't have text, try to get any text from the element
            if not text:
                try:
                    text = await element.inner_text()
                    text = text.strip() if text else ""
                except Exception:
                    pass
            
            # Only skip if we have absolutely no data
            if not post_url and not text:
                return None
            
            # If no post_url, create a hash-based one from text
            if not post_url:
                import hashlib
                text_hash = hashlib.md5(text.encode()).hexdigest()[:12]
                post_url = f"https://www.linkedin.com/feed/post/{text_hash}"
            
            post_data = {
                'post_url': post_url or '',
                'author_url': author_url or '',
                'author_name': author_name or 'Unknown',
                'text': text.strip(),
                'date_posted': date_posted or datetime.now(),
                'likes': likes,
                'comments': comments
            }
            
            # Clean post data
            try:
                post_data = clean_post_data(post_data)
            except Exception as e:
                print(f"Warning: Could not clean post data: {e}")
            
            return post_data
        
        except Exception as e:
            print(f"Error extracting single post: {e}")
            return None
    
    async def scrape(self, keywords: List[str] = None, hashtags: List[str] = None) -> List[Dict]:
        """
        Main scraping method.
        
        Args:
            keywords: List of keywords to search for
            hashtags: List of hashtags to search for
            
        Returns:
            List of scraped post dictionaries
        """
        keywords = keywords or self.config.get('keywords', [])
        hashtags = hashtags or self.config.get('hashtags', [])
        max_posts = self.config.get('scraping', {}).get('max_posts_per_search', 50)
        
        await self.start_browser()
        
        # Ensure page is still valid, recreate if needed
        try:
            if not self.page or self.page.is_closed():
                print("Page was closed, recreating...")
                if self.context:
                    # With persistent context, get existing page or create new one
                    if len(self.context.pages) > 0:
                        self.page = self.context.pages[0]
                    else:
                        self.page = await self.context.new_page()
                else:
                    print("Error: Browser context is not available.")
                    return []
        except Exception as e:
            print(f"Error checking page status: {e}")
            # Try to get a page from context
            try:
                if self.context and len(self.context.pages) > 0:
                    self.page = self.context.pages[0]
                elif self.context:
                    self.page = await self.context.new_page()
                else:
                    return []
            except Exception as recreate_error:
                print(f"Error: Could not recreate page: {recreate_error}")
                return []
        
        # Quick login check - go directly to login page, check if redirected
        try:
            if self.page.is_closed():
                if self.context and len(self.context.pages) > 0:
                    self.page = self.context.pages[0]
                elif self.context:
                    self.page = await self.context.new_page()
            
            print("Checking login status...")
            timeout = self.config.get('scraping', {}).get('timeout', 30000)
            
            # Go directly to login page (faster than feed)
            # If logged in, LinkedIn will redirect us
            try:
                await self.page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded", timeout=timeout)
                await asyncio.sleep(1)  # Minimal wait
                
                # Check if redirected (means logged in)
                current_url = self.page.url.lower()
                if "login" not in current_url:
                    print("Already logged in (redirected from login page)")
                else:
                    print("WARNING: Not logged in - please login manually in the browser")
            except Exception as nav_error:
                # If navigation fails, try to check current URL
                try:
                    current_url = self.page.url.lower()
                    if "feed" in current_url or ("linkedin.com" in current_url and "login" not in current_url):
                        print("Already logged in")
                    else:
                        print(f"WARNING: Navigation error: {nav_error}")
                except:
                    print(f"WARNING: Could not determine login status: {nav_error}")
            
            # Login check complete - proceed with scraping
                
        except Exception as e:
            print(f"WARNING: Error navigating to LinkedIn feed: {e}")
            import traceback
            traceback.print_exc()
            # Try to get page from context if it was closed
            if 'TargetClosedError' in str(type(e)) or 'TargetClosed' in str(e):
                try:
                    print("Attempting to get page from context...")
                    if self.context and len(self.context.pages) > 0:
                        self.page = self.context.pages[0]
                        try:
                            timeout = self.config.get('scraping', {}).get('timeout', 30000)
                            await self.page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=timeout)
                        except Exception:
                            timeout = self.config.get('scraping', {}).get('timeout', 30000)
                            await self.page.goto("https://www.linkedin.com/feed/", wait_until="load", timeout=timeout)
                        await asyncio.sleep(3)
                        current_url = self.page.url.lower()
                        if "login" in current_url or "challenge" in current_url:
                            print("WARNING: Not logged in. Please log in to LinkedIn in the browser window.")
                            return []
                    else:
                        return []
                except Exception as retry_error:
                    print(f"Could not recover from navigation error: {retry_error}")
                    return []
            else:
                return []
        
        # Search for posts
        try:
            print("\nStarting post search...")
            posts = await self.search_posts(keywords, hashtags, max_posts)
            print(f"Post search completed. Found {len(posts)} posts.")
            return posts
        except Exception as e:
            print(f"ERROR: Error during post search: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    async def close(self):
        """Close browser and cleanup."""
        # With persistent context, browser is the context, so we only close context
        # This will save the session data automatically
        # BUT - don't close if we want to keep the session!
        # Only close if explicitly needed
        print("\nSaving browser session...")
        print("   (Browser window will stay open to preserve your login session)")
        print("   You can close it manually when done.")
        
        # Don't close the context - let user close browser manually to preserve session
        # This way the login session is saved
        try:
            if self.playwright:
                # Don't stop playwright - let browser stay open
                pass
        except Exception:
            pass


async def scrape_linkedin(config: dict, keywords: List[str] = None, hashtags: List[str] = None) -> List[Dict]:
    """
    Convenience function to scrape LinkedIn posts.
    
    Args:
        config: Configuration dictionary
        keywords: List of keywords to search for
        hashtags: List of hashtags to search for
        
    Returns:
        List of scraped post dictionaries
    """
    scraper = LinkedInScraper(config)
    try:
        posts = await scraper.scrape(keywords, hashtags)
        return posts
    finally:
        await scraper.close()