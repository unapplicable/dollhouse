#!/usr/bin/env python3
"""
Integration tests for DollHouse application.

Tests cover:
1. Database operations (check_if_show_exists, check_to_download, add_release, etc.)
2. Wishlist matching and filtering logic
3. Regex property checking
4. End-to-end release processing workflow

These tests use a real PostgreSQL database to ensure optimizations work correctly.
"""

import pytest
import psycopg2
import tempfile
import os
from datetime import datetime, timedelta
from dollhouse import DollHouse


# Test database configuration
TEST_DB_CONFIG = {
    'host': 'localhost',
    'database': 'dollhouse_test',
    'user': os.environ.get('PGUSER', 'postgres'),
    'password': os.environ.get('PGPASSWORD', ''),
}


@pytest.fixture(scope='session')
def test_db_connection():
    """Create a test database connection."""
    # Connect to default postgres db to create test db
    conn = psycopg2.connect(
        host=TEST_DB_CONFIG['host'],
        database='postgres',
        user=TEST_DB_CONFIG['user'],
        password=TEST_DB_CONFIG['password']
    )
    conn.autocommit = True
    cur = conn.cursor()
    
    # Drop and recreate test database
    cur.execute("DROP DATABASE IF EXISTS dollhouse_test")
    cur.execute("CREATE DATABASE dollhouse_test")
    cur.close()
    conn.close()
    
    # Connect to test database
    test_conn = psycopg2.connect(
        host=TEST_DB_CONFIG['host'],
        database=TEST_DB_CONFIG['database'],
        user=TEST_DB_CONFIG['user'],
        password=TEST_DB_CONFIG['password']
    )
    
    yield test_conn
    
    test_conn.close()
    
    # Cleanup: drop test database
    conn = psycopg2.connect(
        host=TEST_DB_CONFIG['host'],
        database='postgres',
        user=TEST_DB_CONFIG['user'],
        password=TEST_DB_CONFIG['password']
    )
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("DROP DATABASE IF EXISTS dollhouse_test")
    cur.close()
    conn.close()


@pytest.fixture(scope='session')
def db_schema(test_db_connection):
    """Initialize database schema."""
    cur = test_db_connection.cursor()
    
    # Create tables
    cur.execute("""
        CREATE TABLE releases (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            episode TEXT NOT NULL,
            quality TEXT NOT NULL,
            tags TEXT NOT NULL,
            category TEXT NOT NULL,
            date TIMESTAMP,
            link TEXT
        )
    """)
    
    cur.execute("""
        CREATE TABLE downloads (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            episode TEXT NOT NULL,
            release_id INTEGER
        )
    """)
    
    cur.execute("""
        CREATE TABLE wishlist (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            includeprops TEXT,
            excludeprops TEXT,
            min_episode TEXT
        )
    """)
    
    # Create indexes
    cur.execute("CREATE INDEX idx_releases_link_lower ON releases(LOWER(link))")
    cur.execute("CREATE INDEX idx_releases_title_episode_lower ON releases(LOWER(title), LOWER(episode))")
    cur.execute("CREATE INDEX idx_downloads_title_episode_lower ON downloads(LOWER(title), LOWER(episode))")
    cur.execute("CREATE INDEX idx_releases_date ON releases(date)")
    cur.execute("CREATE INDEX idx_wishlist_title_lower ON wishlist(LOWER(title))")
    
    # Apply Phase 1 optimizations
    with open('phase1_optimizations.sql', 'r') as f:
        cur.execute(f.read())
    
    test_db_connection.commit()
    
    yield test_db_connection
    
    # Cleanup not needed - database will be dropped


@pytest.fixture
def clean_db(db_schema):
    """Clean database before each test."""
    cur = db_schema.cursor()
    cur.execute("TRUNCATE releases, downloads, wishlist RESTART IDENTITY CASCADE")
    db_schema.commit()
    yield db_schema


@pytest.fixture
def dollhouse_instance(clean_db):
    """Create DollHouse instance with test configuration."""
    # Create temporary config file
    config_content = f"""
rss_link = https://test.example.com/rss
database = host={TEST_DB_CONFIG['host']} dbname={TEST_DB_CONFIG['database']} user={TEST_DB_CONFIG['user']} password={TEST_DB_CONFIG['password']}
save_dir = /tmp/dollhouse_test
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
        f.write(config_content)
        config_path = f.name
    
    dh = DollHouse(config_path)
    
    # Override create_connection to use our test connection
    original_create_connection = dh.create_connection
    def test_create_connection():
        return clean_db
    dh.create_connection = test_create_connection
    
    yield dh
    
    # Cleanup
    os.unlink(config_path)


# Test data helpers
def create_sample_release(title="Breaking Bad", episode="S01E01", quality="1080p", 
                         tags="1080p WEB-DL", category="TV", days_ago=1,
                         link="https://example.com/release1"):
    """Helper to create sample release data."""
    date = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d %H:%M:%S")
    return (title, episode, quality, tags, category, date, link)


class TestDatabaseOperations:
    """Test basic database operations."""
    
    def test_add_release(self, dollhouse_instance, clean_db):
        """Test adding a release to database."""
        show = create_sample_release()
        
        row_id = dollhouse_instance.add_release(clean_db, show)
        clean_db.commit()
        
        assert row_id is not None
        
        # Verify release was added
        cur = clean_db.cursor()
        cur.execute("SELECT * FROM releases WHERE id = %s", (row_id,))
        result = cur.fetchone()
        
        assert result is not None
        assert result[1] == "Breaking Bad"
        assert result[2] == "S01E01"
        assert result[3] == "1080p"
    
    def test_check_if_show_exists_false(self, dollhouse_instance, clean_db):
        """Test checking for non-existent release."""
        result = dollhouse_instance.check_if_show_exists(clean_db, "https://example.com/nonexistent")
        assert result is False
    
    def test_check_if_show_exists_true(self, dollhouse_instance, clean_db):
        """Test checking for existing release."""
        show = create_sample_release(link="https://example.com/exists")
        dollhouse_instance.add_release(clean_db, show)
        clean_db.commit()
        
        result = dollhouse_instance.check_if_show_exists(clean_db, "https://example.com/exists")
        assert result is True
    
    def test_check_if_show_exists_case_insensitive(self, dollhouse_instance, clean_db):
        """Test case-insensitive link checking."""
        show = create_sample_release(link="https://EXAMPLE.com/CaseSensitive")
        dollhouse_instance.add_release(clean_db, show)
        clean_db.commit()
        
        result = dollhouse_instance.check_if_show_exists(clean_db, "https://example.com/casesensitive")
        assert result is True
    
    def test_add_downloads(self, dollhouse_instance, clean_db):
        """Test adding a download record."""
        # First add a release
        release = create_sample_release()
        release_id = dollhouse_instance.add_release(clean_db, release)
        clean_db.commit()
        
        # Add download
        download = ("Breaking Bad", "S01E01", release_id)
        download_id = dollhouse_instance.add_downloads(clean_db, download)
        clean_db.commit()
        
        assert download_id is not None
        
        # Verify download was added
        cur = clean_db.cursor()
        cur.execute("SELECT * FROM downloads WHERE id = %s", (download_id,))
        result = cur.fetchone()
        
        assert result is not None
        assert result[1] == "Breaking Bad"
        assert result[2] == "S01E01"
        assert result[3] == release_id
    
    def test_check_to_download_true(self, dollhouse_instance, clean_db):
        """Test checking if episode should be downloaded (not yet downloaded)."""
        result = dollhouse_instance.check_to_download(clean_db, "Breaking Bad", "S01E01")
        assert result is True
    
    def test_check_to_download_false(self, dollhouse_instance, clean_db):
        """Test checking if episode should be downloaded (already downloaded)."""
        # Add a download
        download = ("Breaking Bad", "S01E01", 1)
        dollhouse_instance.add_downloads(clean_db, download)
        clean_db.commit()
        
        result = dollhouse_instance.check_to_download(clean_db, "Breaking Bad", "S01E01")
        assert result is False
    
    def test_check_to_download_case_insensitive(self, dollhouse_instance, clean_db):
        """Test case-insensitive download checking."""
        download = ("Breaking Bad", "S01E01", 1)
        dollhouse_instance.add_downloads(clean_db, download)
        clean_db.commit()
        
        result = dollhouse_instance.check_to_download(clean_db, "BREAKING BAD", "s01e01")
        assert result is False
    
    def test_get_wishlist(self, dollhouse_instance, clean_db):
        """Test retrieving wishlist."""
        cur = clean_db.cursor()
        cur.execute("""
            INSERT INTO wishlist(title, min_episode, includeprops, excludeprops)
            VALUES ('Breaking Bad', 'S01E01', '1080p', 'HDCAM')
        """)
        clean_db.commit()
        
        wishlist = dollhouse_instance.get_wishlist(clean_db)
        
        assert len(wishlist) == 1
        assert wishlist[0][0] == "Breaking Bad"
        assert wishlist[0][1] == "S01E01"
        assert wishlist[0][2] == "1080p"
        assert wishlist[0][3] == "HDCAM"


class TestWishlistMatching:
    """Test wishlist matching and release finding logic."""
    
    def test_find_releases_no_wishlist(self, dollhouse_instance, clean_db):
        """Test find_releases with empty wishlist."""
        # Add some releases
        show1 = create_sample_release()
        dollhouse_instance.add_release(clean_db, show1)
        clean_db.commit()
        
        # Run find_releases (should do nothing with empty wishlist)
        dollhouse_instance.find_releases(clean_db)
        
        # No downloads should be created
        cur = clean_db.cursor()
        cur.execute("SELECT COUNT(*) FROM downloads")
        count = cur.fetchone()[0]
        assert count == 0
    
    def test_find_releases_basic_match(self, dollhouse_instance, clean_db):
        """Test basic wishlist matching."""
        # Add wishlist item
        cur = clean_db.cursor()
        cur.execute("""
            INSERT INTO wishlist(title, min_episode, includeprops, excludeprops)
            VALUES ('Breaking Bad', 'S01E01', NULL, NULL)
        """)
        
        # Add matching release (recent)
        show = create_sample_release(
            title="Breaking Bad",
            episode="S01E02",
            link="https://example.com/bb-s01e02"
        )
        dollhouse_instance.add_release(clean_db, show)
        clean_db.commit()
        
        # Mock download_episode to avoid actual download
        def mock_download(link):
            return True
        dollhouse_instance.download_episode = mock_download
        
        # Run find_releases
        dollhouse_instance.find_releases(clean_db)
        
        # Verify download was recorded
        cur.execute("SELECT COUNT(*) FROM downloads WHERE title = 'Breaking Bad' AND episode = 'S01E02'")
        count = cur.fetchone()[0]
        assert count == 1
    
    def test_find_releases_min_episode_filter(self, dollhouse_instance, clean_db):
        """Test min_episode filtering."""
        # Add wishlist with min_episode
        cur = clean_db.cursor()
        cur.execute("""
            INSERT INTO wishlist(title, min_episode, includeprops, excludeprops)
            VALUES ('Breaking Bad', 'S02E01', NULL, NULL)
        """)
        
        # Add release below minimum (should be ignored)
        show1 = create_sample_release(
            title="Breaking Bad",
            episode="S01E05",
            link="https://example.com/bb-s01e05"
        )
        dollhouse_instance.add_release(clean_db, show1)
        
        # Add release at minimum (should be downloaded)
        show2 = create_sample_release(
            title="Breaking Bad",
            episode="S02E01",
            link="https://example.com/bb-s02e01"
        )
        dollhouse_instance.add_release(clean_db, show2)
        
        # Add release above minimum (should be downloaded)
        show3 = create_sample_release(
            title="Breaking Bad",
            episode="S02E05",
            link="https://example.com/bb-s02e05"
        )
        dollhouse_instance.add_release(clean_db, show3)
        clean_db.commit()
        
        # Mock download
        def mock_download(link):
            return True
        dollhouse_instance.download_episode = mock_download
        
        # Run find_releases
        dollhouse_instance.find_releases(clean_db)
        
        # Verify only S02+ episodes were downloaded
        cur.execute("SELECT episode FROM downloads WHERE title = 'Breaking Bad' ORDER BY episode")
        episodes = [row[0] for row in cur.fetchall()]
        assert "S01E05" not in episodes
        assert "S02E01" in episodes
        assert "S02E05" in episodes
    
    def test_find_releases_include_props(self, dollhouse_instance, clean_db):
        """Test includeprops filtering."""
        # Add wishlist with include filter
        cur = clean_db.cursor()
        cur.execute("""
            INSERT INTO wishlist(title, min_episode, includeprops, excludeprops)
            VALUES ('Breaking Bad', NULL, '1080p', NULL)
        """)
        
        # Add 1080p release (should match)
        show1 = create_sample_release(
            title="Breaking Bad",
            episode="S01E01",
            tags="1080p WEB-DL",
            link="https://example.com/bb-1080p"
        )
        dollhouse_instance.add_release(clean_db, show1)
        
        # Add 720p release (should not match)
        show2 = create_sample_release(
            title="Breaking Bad",
            episode="S01E02",
            quality="720p",
            tags="720p WEB-DL",
            link="https://example.com/bb-720p"
        )
        dollhouse_instance.add_release(clean_db, show2)
        clean_db.commit()
        
        # Mock download
        def mock_download(link):
            return True
        dollhouse_instance.download_episode = mock_download
        
        # Run find_releases
        dollhouse_instance.find_releases(clean_db)
        
        # Verify only 1080p was downloaded
        cur.execute("SELECT episode FROM downloads WHERE title = 'Breaking Bad'")
        episodes = [row[0] for row in cur.fetchall()]
        assert "S01E01" in episodes
        assert "S01E02" not in episodes
    
    def test_find_releases_exclude_props(self, dollhouse_instance, clean_db):
        """Test excludeprops filtering."""
        # Add wishlist with exclude filter
        cur = clean_db.cursor()
        cur.execute("""
            INSERT INTO wishlist(title, min_episode, includeprops, excludeprops)
            VALUES ('Breaking Bad', NULL, NULL, 'HDCAM')
        """)
        
        # Add good release (should match)
        show1 = create_sample_release(
            title="Breaking Bad",
            episode="S01E01",
            tags="1080p WEB-DL",
            link="https://example.com/bb-webdl"
        )
        dollhouse_instance.add_release(clean_db, show1)
        
        # Add HDCAM release (should not match)
        show2 = create_sample_release(
            title="Breaking Bad",
            episode="S01E02",
            tags="1080p HDCAM",
            link="https://example.com/bb-hdcam"
        )
        dollhouse_instance.add_release(clean_db, show2)
        clean_db.commit()
        
        # Mock download
        def mock_download(link):
            return True
        dollhouse_instance.download_episode = mock_download
        
        # Run find_releases
        dollhouse_instance.find_releases(clean_db)
        
        # Verify only non-HDCAM was downloaded
        cur.execute("SELECT episode FROM downloads WHERE title = 'Breaking Bad'")
        episodes = [row[0] for row in cur.fetchall()]
        assert "S01E01" in episodes
        assert "S01E02" not in episodes
    
    def test_find_releases_old_releases_ignored(self, dollhouse_instance, clean_db):
        """Test that releases older than 3 days are ignored."""
        # Add wishlist
        cur = clean_db.cursor()
        cur.execute("""
            INSERT INTO wishlist(title, min_episode, includeprops, excludeprops)
            VALUES ('Breaking Bad', NULL, NULL, NULL)
        """)
        
        # Add old release (4 days ago - should be ignored)
        show1 = create_sample_release(
            title="Breaking Bad",
            episode="S01E01",
            days_ago=4,
            link="https://example.com/bb-old"
        )
        dollhouse_instance.add_release(clean_db, show1)
        
        # Add recent release (1 day ago - should be downloaded)
        show2 = create_sample_release(
            title="Breaking Bad",
            episode="S01E02",
            days_ago=1,
            link="https://example.com/bb-new"
        )
        dollhouse_instance.add_release(clean_db, show2)
        clean_db.commit()
        
        # Mock download
        def mock_download(link):
            return True
        dollhouse_instance.download_episode = mock_download
        
        # Run find_releases
        dollhouse_instance.find_releases(clean_db)
        
        # Verify only recent release was downloaded
        cur.execute("SELECT episode FROM downloads WHERE title = 'Breaking Bad'")
        episodes = [row[0] for row in cur.fetchall()]
        assert "S01E01" not in episodes
        assert "S01E02" in episodes
    
    def test_find_releases_no_duplicate_downloads(self, dollhouse_instance, clean_db):
        """Test that same episode is not downloaded twice."""
        # Add wishlist
        cur = clean_db.cursor()
        cur.execute("""
            INSERT INTO wishlist(title, min_episode, includeprops, excludeprops)
            VALUES ('Breaking Bad', NULL, NULL, NULL)
        """)
        
        # Add release
        show = create_sample_release(
            title="Breaking Bad",
            episode="S01E01",
            link="https://example.com/bb-s01e01"
        )
        release_id = dollhouse_instance.add_release(clean_db, show)
        clean_db.commit()
        
        # Mock download
        download_count = [0]
        def mock_download(link):
            download_count[0] += 1
            return True
        dollhouse_instance.download_episode = mock_download
        
        # Run find_releases first time
        dollhouse_instance.find_releases(clean_db)
        assert download_count[0] == 1
        
        # Run find_releases again (should not download again)
        dollhouse_instance.find_releases(clean_db)
        assert download_count[0] == 1  # Still 1, not 2
        
        # Verify only one download record
        cur.execute("SELECT COUNT(*) FROM downloads WHERE title = 'Breaking Bad' AND episode = 'S01E01'")
        count = cur.fetchone()[0]
        assert count == 1


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_empty_database(self, dollhouse_instance, clean_db):
        """Test operations on empty database."""
        assert dollhouse_instance.check_if_show_exists(clean_db, "any link") is False
        assert dollhouse_instance.check_to_download(clean_db, "any title", "any episode") is True
        
        wishlist = dollhouse_instance.get_wishlist(clean_db)
        assert len(wishlist) == 0
    
    def test_special_characters_in_title(self, dollhouse_instance, clean_db):
        """Test handling of special characters."""
        show = create_sample_release(
            title="It's Always Sunny in Philadelphia",
            episode="S01E01",
            link="https://example.com/sunny"
        )
        release_id = dollhouse_instance.add_release(clean_db, show)
        clean_db.commit()
        
        assert release_id is not None
        assert dollhouse_instance.check_if_show_exists(clean_db, "https://example.com/sunny") is True
    
    def test_unicode_in_title(self, dollhouse_instance, clean_db):
        """Test handling of unicode characters."""
        show = create_sample_release(
            title="Café René",
            episode="S01E01",
            link="https://example.com/cafe"
        )
        release_id = dollhouse_instance.add_release(clean_db, show)
        
        # Add download for exact unicode match
        download = ("Café René", "S01E01", release_id)
        dollhouse_instance.add_downloads(clean_db, download)
        clean_db.commit()
        
        assert release_id is not None
        
        # Test exact unicode check (PostgreSQL LOWER doesn't normalize unicode the same)
        result = dollhouse_instance.check_to_download(clean_db, "Café René", "S01E01")
        assert result is False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
