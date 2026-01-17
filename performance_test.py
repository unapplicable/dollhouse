#!/usr/bin/env python3
"""
Performance benchmark script for DollHouse optimizations.
Replicates production data volumes (4024 releases, 830 downloads, 23 wishlist, 909 recent).
"""

import psycopg2
import time
import statistics
from datetime import datetime, timedelta
import random

# Test database configuration
TEST_DB = {
    'host': 'localhost',
    'database': 'dollhouse_perftest',
    'user': 'lauri',
    'password': 'test'
}

# Production-like data volumes
TARGET_RELEASES = 4024
TARGET_DOWNLOADS = 830
TARGET_WISHLIST = 23
TARGET_RECENT = 909  # Releases within 3 days

# Sample data patterns from production
SAMPLE_TITLES = [
    'Billions', 'Episodes', 'Homeland', 'Jane The Virgin', 'Ray Donovan',
    'The Walking Dead', 'Game of Thrones', 'Breaking Bad', 'Better Call Saul',
    'The Wire', 'Stranger Things', 'The Crown', 'Ozark', 'Dark', 'Narcos',
    'House of Cards', 'Westworld', 'Mr Robot', 'The Handmaids Tale', 'Peaky Blinders'
]

QUALITIES = ['1080p', '720p', '2160p']
TAGS_PATTERNS = [
    '1080p WEB-DL H264',
    '720p HDTV x264',
    '1080p BluRay x264',
    '720p WEB H264',
    '2160p WEB-DL H265',
    '1080p AMZN WEB-DL',
]

def create_test_database():
    """Create fresh test database."""
    print("Creating test database...")
    conn = psycopg2.connect(
        host=TEST_DB['host'],
        database='postgres',
        user=TEST_DB['user'],
        password=TEST_DB['password']
    )
    conn.autocommit = True
    cur = conn.cursor()
    
    cur.execute(f"DROP DATABASE IF EXISTS {TEST_DB['database']}")
    cur.execute(f"CREATE DATABASE {TEST_DB['database']}")
    cur.close()
    conn.close()
    print("✓ Test database created")

def setup_schema(conn):
    """Create tables and indexes."""
    print("Setting up schema...")
    cur = conn.cursor()
    
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
    
    conn.commit()
    print("✓ Schema created")

def populate_data(conn):
    """Populate with production-like data volumes."""
    print(f"\nPopulating test data (this may take a minute)...")
    cur = conn.cursor()
    
    # Insert wishlist (23 items)
    print(f"  Inserting {TARGET_WISHLIST} wishlist items...")
    wishlist_titles = []
    for i in range(TARGET_WISHLIST):
        title = SAMPLE_TITLES[i % len(SAMPLE_TITLES)]
        wishlist_titles.append(title)
        season = random.randint(1, 7)
        episode = random.randint(1, 12)
        cur.execute("""
            INSERT INTO wishlist(title, min_episode, includeprops, excludeprops)
            VALUES (%s, %s, %s, %s)
        """, (title, f"S{season:02d}E{episode:02d}", "(1080p|720p)", "(SPANISH|FRENCH|GERMAN)"))
    
    # Insert releases (4024 total, 909 recent)
    print(f"  Inserting {TARGET_RELEASES} releases...")
    recent_releases = []
    old_releases = TARGET_RELEASES - TARGET_RECENT
    
    # Old releases (more than 3 days ago)
    for i in range(old_releases):
        title = random.choice(SAMPLE_TITLES)
        season = random.randint(1, 10)
        episode = random.randint(1, 24)
        quality = random.choice(QUALITIES)
        tags = f"{quality} {random.choice(TAGS_PATTERNS)}"
        days_ago = random.randint(4, 90)
        date = datetime.now() - timedelta(days=days_ago)
        
        cur.execute("""
            INSERT INTO releases(title, episode, quality, tags, category, date, link)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (title, f"S{season:02d}E{episode:02d}", quality, tags, "TV", 
              date, f"https://example.com/release{i}"))
    
    # Recent releases (within 3 days) - some matching wishlist
    for i in range(TARGET_RECENT):
        # 40% chance to match wishlist for realistic testing
        if random.random() < 0.4:
            title = random.choice(wishlist_titles)
        else:
            title = random.choice(SAMPLE_TITLES)
        
        season = random.randint(1, 10)
        episode = random.randint(1, 24)
        quality = random.choice(QUALITIES)
        tags = f"{quality} {random.choice(TAGS_PATTERNS)}"
        days_ago = random.uniform(0, 3)
        date = datetime.now() - timedelta(days=days_ago)
        
        cur.execute("""
            INSERT INTO releases(title, episode, quality, tags, category, date, link)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (title, f"S{season:02d}E{episode:02d}", quality, tags, "TV", 
              date, f"https://example.com/release{old_releases + i}"))
        recent_releases.append((title, f"S{season:02d}E{episode:02d}", cur.fetchone()[0]))
    
    # Insert downloads (830 items)
    print(f"  Inserting {TARGET_DOWNLOADS} downloads...")
    for i in range(TARGET_DOWNLOADS):
        # Pick from recent releases
        if recent_releases:
            title, episode, release_id = random.choice(recent_releases)
            cur.execute("""
                INSERT INTO downloads(title, episode, release_id)
                VALUES (%s, %s, %s)
            """, (title, episode, release_id))
    
    conn.commit()
    
    # Verify counts
    cur.execute("SELECT COUNT(*) FROM releases")
    releases_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM downloads")
    downloads_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM wishlist")
    wishlist_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM releases WHERE date > NOW() - INTERVAL '3 days'")
    recent_count = cur.fetchone()[0]
    
    print(f"\n✓ Data populated:")
    print(f"  Releases: {releases_count}")
    print(f"  Downloads: {downloads_count}")
    print(f"  Wishlist: {wishlist_count}")
    print(f"  Recent releases: {recent_count}")

def apply_optimizations(conn):
    """Apply Phase 1 optimization functions."""
    print("\nApplying Phase 1 optimizations...")
    cur = conn.cursor()
    with open('phase1_optimizations.sql', 'r') as f:
        cur.execute(f.read())
    conn.commit()
    print("✓ Optimizations applied")

def benchmark_check_release_exists(conn, optimized=False):
    """Benchmark duplicate checking."""
    cur = conn.cursor()
    test_links = [f"https://example.com/release{i}" for i in range(100)]
    
    timings = []
    for link in test_links:
        start = time.time()
        if optimized:
            cur.execute("SELECT check_release_exists(%s)", (link,))
        else:
            cur.execute("SELECT * FROM releases WHERE lower(link)=lower(%s)", (link,))
            rows = cur.fetchall()
            result = len(rows) > 0
        end = time.time()
        timings.append((end - start) * 1000)  # Convert to ms
    
    return timings

def benchmark_check_to_download(conn, optimized=False):
    """Benchmark download checking."""
    cur = conn.cursor()
    
    # Get some sample title/episode combinations
    cur.execute("SELECT DISTINCT title, episode FROM releases LIMIT 100")
    test_cases = cur.fetchall()
    
    timings = []
    for title, episode in test_cases:
        start = time.time()
        if optimized:
            cur.execute("SELECT is_not_downloaded(%s, %s)", (title, episode))
        else:
            cur.execute("""
                SELECT * FROM downloads 
                WHERE lower(title)=lower(%s) AND lower(episode)=lower(%s) 
                ORDER BY episode DESC
            """, (title, episode))
            rows = cur.fetchall()
            result = len(rows) == 0
        end = time.time()
        timings.append((end - start) * 1000)
    
    return timings

def benchmark_find_releases(conn, optimized=False):
    """Benchmark wishlist matching - the big one."""
    cur = conn.cursor()
    
    timings = []
    for i in range(10):  # Run 10 times for statistical significance
        start = time.time()
        
        if optimized:
            # Optimized: single query
            cur.execute("SELECT * FROM find_matching_releases()")
            results = cur.fetchall()
        else:
            # Original: N+1 queries with Python filtering
            cur.execute("SELECT title, min_episode, includeprops, excludeprops FROM wishlist")
            wishlist = cur.fetchall()
            
            all_results = []
            for wish in wishlist:
                title, min_episode, includeprops, excludeprops = wish
                if min_episode is None:
                    min_episode = ""
                
                cur.execute("""
                    SELECT id, title, episode, quality, link, tags 
                    FROM releases 
                    WHERE lower(title)=lower(%s) 
                    AND date > NOW() - INTERVAL '3 days' 
                    AND lower(episode)>=lower(%s) 
                    ORDER BY title, episode, quality
                """, (title, min_episode))
                
                rows = cur.fetchall()
                for row in rows:
                    # Python regex matching
                    tags = row[5]
                    if includeprops or excludeprops:
                        import re
                        if includeprops and excludeprops:
                            if re.search(includeprops, tags, re.IGNORECASE) and not re.search(excludeprops, tags, re.IGNORECASE):
                                # Check if already downloaded
                                cur.execute("""
                                    SELECT * FROM downloads 
                                    WHERE lower(title)=lower(%s) AND lower(episode)=lower(%s)
                                """, (row[1], row[2]))
                                if len(cur.fetchall()) == 0:
                                    all_results.append(row)
        
        end = time.time()
        timings.append((end - start) * 1000)
    
    return timings

def print_results(name, original_timings, optimized_timings):
    """Print benchmark results."""
    orig_avg = statistics.mean(original_timings)
    orig_med = statistics.median(original_timings)
    orig_std = statistics.stdev(original_timings) if len(original_timings) > 1 else 0
    
    opt_avg = statistics.mean(optimized_timings)
    opt_med = statistics.median(optimized_timings)
    opt_std = statistics.stdev(optimized_timings) if len(optimized_timings) > 1 else 0
    
    improvement = ((orig_avg - opt_avg) / orig_avg) * 100
    speedup = orig_avg / opt_avg
    
    print(f"\n{'='*70}")
    print(f"{name}")
    print(f"{'='*70}")
    print(f"{'Metric':<20} {'Original':<20} {'Optimized':<20} {'Change':<10}")
    print(f"{'-'*70}")
    print(f"{'Average (ms)':<20} {orig_avg:>18.3f} {opt_avg:>18.3f} {improvement:>8.1f}%")
    print(f"{'Median (ms)':<20} {orig_med:>18.3f} {opt_med:>18.3f}")
    print(f"{'Std Dev (ms)':<20} {orig_std:>18.3f} {opt_std:>18.3f}")
    print(f"{'Speedup':<20} {'1.00x':>18} {speedup:>18.2f}x")
    
    if improvement > 0:
        print(f"\n✓ GAIN: {improvement:.1f}% faster ({speedup:.2f}x speedup)")
    else:
        print(f"\n✗ LOSS: {abs(improvement):.1f}% slower")

def main():
    print("="*70)
    print("DollHouse Performance Benchmark")
    print("Production-like data: 4024 releases, 830 downloads, 23 wishlist")
    print("="*70)
    
    # Setup
    create_test_database()
    conn = psycopg2.connect(**TEST_DB)
    setup_schema(conn)
    populate_data(conn)
    
    # Run ANALYZE for accurate query planning
    print("\nAnalyzing tables...")
    cur = conn.cursor()
    cur.execute("ANALYZE releases")
    cur.execute("ANALYZE downloads")
    cur.execute("ANALYZE wishlist")
    conn.commit()
    print("✓ Analysis complete")
    
    # Benchmark original implementation
    print("\n" + "="*70)
    print("PHASE 1: Testing ORIGINAL implementation")
    print("="*70)
    
    print("\nBenchmarking check_release_exists (100 iterations)...")
    orig_check_exists = benchmark_check_release_exists(conn, optimized=False)
    
    print("Benchmarking check_to_download (100 iterations)...")
    orig_check_download = benchmark_check_to_download(conn, optimized=False)
    
    print("Benchmarking find_releases (10 iterations)...")
    orig_find_releases = benchmark_find_releases(conn, optimized=False)
    
    # Apply optimizations
    apply_optimizations(conn)
    
    # Benchmark optimized implementation
    print("\n" + "="*70)
    print("PHASE 2: Testing OPTIMIZED implementation")
    print("="*70)
    
    print("\nBenchmarking check_release_exists (100 iterations)...")
    opt_check_exists = benchmark_check_release_exists(conn, optimized=True)
    
    print("Benchmarking check_to_download (100 iterations)...")
    opt_check_download = benchmark_check_to_download(conn, optimized=True)
    
    print("Benchmarking find_releases (10 iterations)...")
    opt_find_releases = benchmark_find_releases(conn, optimized=True)
    
    # Print results
    print("\n" + "="*70)
    print("RESULTS SUMMARY")
    print("="*70)
    
    print_results("Phase 1.1: check_release_exists()", orig_check_exists, opt_check_exists)
    print_results("Phase 1.2: check_to_download()", orig_check_download, opt_check_download)
    print_results("Phase 1.3: find_releases()", orig_find_releases, opt_find_releases)
    
    # Overall calculation
    total_orig = statistics.mean(orig_check_exists) + statistics.mean(orig_check_download) + statistics.mean(orig_find_releases)
    total_opt = statistics.mean(opt_check_exists) + statistics.mean(opt_check_download) + statistics.mean(opt_find_releases)
    total_improvement = ((total_orig - total_opt) / total_orig) * 100
    
    print(f"\n{'='*70}")
    print("OVERALL PHASE 1 IMPACT")
    print(f"{'='*70}")
    print(f"Total original time:   {total_orig:>10.2f} ms")
    print(f"Total optimized time:  {total_opt:>10.2f} ms")
    print(f"Overall improvement:   {total_improvement:>10.1f}%")
    print(f"Overall speedup:       {total_orig/total_opt:>10.2f}x")
    
    # Cleanup
    conn.close()
    print(f"\n{'='*70}")
    print("Benchmark complete!")
    print(f"{'='*70}\n")

if __name__ == '__main__':
    main()
