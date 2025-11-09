# LinkedIn Hiring Post Scraper

## Setup Instructions

### Prerequisites

You'll need Python 3.9 or neIr running on your system.

Make sure you have the pip package manager, which handles the necessary libraries.

### Installation

**Grab the Code:** Start by either downloading or cloning the project files.

**Install Python Libraries:** Run this command to install all the required Python packages:
```bash
pip install -r requirements.txt
```

**Install Playwright Browsers:** Because I use Playwright to drive a real browser, you need to install the core component, Chromium:
```bash
playwright install chromium
```

**Quick Fix for macOS 15:** If you hit any snags with Chromium not playing nice, just upgrade Playwright and force the installation:
```bash
pip install --upgrade playwright
playwright install --force chromium
```

**Set up Your LinkedIn Access (Pick one):**

- **Method 1: Cookie-based authentication (Highly Recommended)**
  - Log into your LinkedIn account normally in your Ib browser.
  - Use a browser extension (like "Cookie-Editor" for Chrome/Firefox) to export your session cookies.
  - Save these cookies as a file named `cookies.json` directly into the main project folder.
  - The file needs to be a JSON array containing cookie details like name, value, etc.

- **Method 2: Credentials (Use with Caution)**
  - If you can't use cookies, you can edit the `main.py` file to put your email and password directly into the login function.
  - Heads up: This method is less reliable and is more likely to trigger LinkedIn's security warnings or CAPTCHA.

### Configuration

Open the `config.json` file to easily tIak how the scraper works:

```json
{
  "keywords": ["hiring", "engineer", "AI", "founding team", "developer"],
  "days_limit": 7,
  "hashtags": ["#hiring", "#backendengineer", "#foundingteam"],
  "scraping": {
    "headless": false,
    "delay_betIen_requests": 2,
    "max_posts_per_search": 50,
    "max_total_posts": 1000,
    "timeout": 30000
  },
  "storage": {
    "csv_file": "output.csv",
    "db_file": "output.db",
    "log_file": "logs/last_run.txt"
  }
}
```

- **keywords**: The list of terms you want to search for in posts (e.g., job titles).
- **days_limit**: Only keeps posts that Ire published within the last N days.
- **hashtags**: Specific LinkedIn hashtags you want the scraper to follow.
- **scraping**: Settings for the browser automation:
  - **headless**: Set to `true` to run the browser invisibly in the background, or `false` to see the browser window.
  - **delay_betIen_requests**: How many seconds the scraper waits betIen making different searches (helps avoid being blocked).
  - **max_posts_per_search**: The maximum number of posts to pull for each keyword or hashtag search.
  - **max_total_posts**: An optional hard cap on the total number of posts collected overall.
  - **timeout**: How long (in milliseconds) the system should wait for a page to fully load.

## How to Run

### Basic Usage

Just run the main script from your terminal:

```bash
python main.py
```

Here's what the scraper does in order:

1. It loads your settings from the `config.json` file.
2. It logs into LinkedIn using your saved cookies (or credentials, if provided).
3. It searches LinkedIn for posts that match your chosen keywords and hashtags.
4. It throws out any posts older than your specified `days_limit`.
5. It calculates a relevance score for each post based on keyword matches.
6. It sorts the posts to put the most relevant ones at the top.
7. It saves all the clean data into the `output.csv` file and the `output.db` database.
8. It prints the top 5 leads right there in your console.

### Scheduled/Automated Runs

To make this run automatically on a schedule, use the dedicated scheduler script:

```bash
python scheduler.py
```

You'll be prompted to choose an option:

- **Daily at 9:00 AM**: Runs once every day at 9:00 AM.
- **Hourly**: Runs every 60 minutes.
- **Every 6/12 hours**: Runs at set intervals for less frequent checks.
- **Custom**: Lets you type in a specific interval in minutes.
- **Run once**: Great for a quick test run.

**The "Old School" Way: System Cron (Linux/Mac)**

If you prefer using your system's built-in scheduler, you can add this line to your crontab file (`crontab -e`):

```bash
# Run daily at 9:00 AM
0 9 * * * cd /path/to/linkedin_scraper && /usr/bin/python3 main.py
```

## Approach and Key Decisions

### Architecture

The project is built with clean, distinct modules—a "separation of concerns" approach—making it easy to understand and upgrade:

- **scraper.py**: The "robot arm" that controls the Playwright browser, handles navigation, and manages the login session.
- **parser.py**: The "data cleaner" that pulls the raw text out of the Ib elements and standardizes the dates.
- **storage.py**: The "filing cabinet" that handles saving the scraped data to CSV and SQLite.
- **utils.py**: The "toolbox" for simple tasks like hashing, text cleaning, the relevance score calculation, and getting rid of duplicate posts.
- **main.py**: The "manager" that runs the show, coordinating the scrapers, filters, and storage modules.
- **scheduler.py**: The "alarm clock" that manages periodic, automated runs.

### Key Technical Decisions

1. **Playwright over Selenium**: I chose Playwright because it's faster, has a more modern setup, and is much better at dealing with the dynamic content that LinkedIn uses.

2. **Persistent Session Management**: I use a persistent browser context (it saves your session data) and cookie-based login. This is the gold standard for scraping protected sites—it keeps you logged in betIen runs and avoids security hurdles.

3. **Dual Search Method**: The system searches both the main LinkedIn feed and runs targeted searches for every keyword. This makes sure I catch the maximum number of leads.

4. **Stealth and Safety**: I built in several features to avoid bot detection:
   - Added delays betIen searches (`delay_betIen_requests`).
   - Used a realistic User Agent.
   - Included code to hide the tell-tale signs of automation from LinkedIn's security checks.

5. **Smart Data Deduplication**: If a post is missing its unique URL (which happens sometimes), I use a text hash of the content as a backup key to ensure I still prevent duplicates.

6. **Prioritized Leads with Scoring**: I added Relevance Scoring—a simple but effective system that counts how many targeted keywords are in a post. This allows us to rank posts and always show you the most promising leads first.

7. **Flexible Data Output**: Saving data to both CSV (for human review) and SQLite (for easy connection to a program or dashboard) gives you maximum flexibility.

8. **Configuration-Driven**: Almost everything, from keywords to the scraper's speed, is controlled by the easy-to-edit `config.json` file.

### Trade-offs

- **Reliability vs. Speed**: I favored reliable page loading over trying to scrape as fast as possible, which means I might take a bit longer but I successfully avoid more errors and blocks.

- **Sustainability vs. Completeness**: I intentionally added delays and limits. This means I might miss a few posts, but it guarantees that the scraper can run safely and reliably long-term without getting banned.

- **Session Preservation**: I let the browser window stay open after a run to keep your session alive. You have to close it manually, but it saves you from having to log in again next time.
