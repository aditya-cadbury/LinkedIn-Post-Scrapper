"""
Storage module for saving posts to CSV and SQLite database.
"""
import csv
import sqlite3
import os
from datetime import datetime
from typing import List, Dict
import json


class StorageManager:
    """
    Manages storage of posts to both CSV and SQLite formats.
    """
    
    def __init__(self, csv_file: str = "output.csv", db_file: str = "output.db"):
        """
        Initialize storage manager.
        
        Args:
            csv_file: Path to CSV output file
            db_file: Path to SQLite database file
        """
        self.csv_file = csv_file
        self.db_file = db_file
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database with posts table."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                author TEXT,
                author_url TEXT,
                post_url TEXT UNIQUE,
                text_snippet TEXT,
                full_text TEXT,
                score INTEGER,
                likes INTEGER DEFAULT 0,
                comments INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create index on post_url for faster lookups
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_post_url ON posts(post_url)
        ''')
        
        conn.commit()
        conn.close()
    
    def save_posts(self, posts: List[Dict], append: bool = False):
        """
        Save posts to both CSV and SQLite.
        
        Args:
            posts: List of post dictionaries
            append: If True, append to existing files; otherwise overwrite
        """
        if not posts:
            print("No posts to save.")
            return
        
        self._save_to_csv(posts, append)
        self._save_to_db(posts)
        print(f"Saved {len(posts)} posts to {self.csv_file} and {self.db_file}")
    
    def _save_to_csv(self, posts: List[Dict], append: bool):
        """Save posts to CSV file."""
        if not posts:
            return
        
        # Define CSV columns
        fieldnames = ['date', 'author', 'author_url', 'post_url', 'text_snippet', 'score', 'likes', 'comments']
        
        mode = 'a' if append and os.path.exists(self.csv_file) else 'w'
        
        with open(self.csv_file, mode, newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            if mode == 'w':
                writer.writeheader()
            
            for post in posts:
                row = {
                    'date': post.get('date_posted', datetime.now()).strftime('%Y-%m-%d') if isinstance(post.get('date_posted'), datetime) else str(post.get('date_posted', '')),
                    'author': post.get('author_name', ''),
                    'author_url': post.get('author_url', ''),
                    'post_url': post.get('post_url', ''),
                    'text_snippet': post.get('text_snippet', ''),
                    'score': post.get('score', 0),
                    'likes': post.get('likes', 0),
                    'comments': post.get('comments', 0)
                }
                writer.writerow(row)
    
    def _save_to_db(self, posts: List[Dict]):
        """Save posts to SQLite database."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        for post in posts:
            try:
                date_posted = post.get('date_posted', datetime.now())
                if isinstance(date_posted, datetime):
                    date_str = date_posted.strftime('%Y-%m-%d')
                else:
                    date_str = str(date_posted)
                
                cursor.execute('''
                    INSERT OR REPLACE INTO posts 
                    (date, author, author_url, post_url, text_snippet, full_text, score, likes, comments)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    date_str,
                    post.get('author_name', ''),
                    post.get('author_url', ''),
                    post.get('post_url', ''),
                    post.get('text_snippet', ''),
                    post.get('text', ''),
                    post.get('score', 0),
                    post.get('likes', 0),
                    post.get('comments', 0)
                ))
            except sqlite3.IntegrityError:
                # Post already exists, skip
                continue
            except Exception as e:
                print(f"Error saving post to database: {e}")
                continue
        
        conn.commit()
        conn.close()
    
    def get_recent_posts(self, limit: int = 10) -> List[Dict]:
        """
        Retrieve recent posts from database.
        
        Args:
            limit: Maximum number of posts to retrieve
            
        Returns:
            List of post dictionaries
        """
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT date, author, author_url, post_url, text_snippet, score, likes, comments
            FROM posts
            ORDER BY created_at DESC
            LIMIT ?
        ''', (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        posts = []
        for row in rows:
            posts.append({
                'date': row[0],
                'author': row[1],
                'author_url': row[2],
                'post_url': row[3],
                'text_snippet': row[4],
                'score': row[5],
                'likes': row[6],
                'comments': row[7]
            })
        
        return posts
    
    def post_exists(self, post_url: str) -> bool:
        """
        Check if a post already exists in the database.
        
        Args:
            post_url: URL of the post to check
            
        Returns:
            True if post exists, False otherwise
        """
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute('SELECT 1 FROM posts WHERE post_url = ?', (post_url,))
        exists = cursor.fetchone() is not None
        
        conn.close()
        return exists


def write_log(log_file: str, message: str):
    """
    Write a log message to file.
    
    Args:
        log_file: Path to log file
        message: Log message to write
    """
    os.makedirs(os.path.dirname(log_file) if os.path.dirname(log_file) else '.', exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_entry = f"[{timestamp}] {message}\n"
    
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(log_entry)

