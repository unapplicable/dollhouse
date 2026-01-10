-- Migration script from SQLite to PostgreSQL
-- Run this script in PostgreSQL to create the database schema
-- Optimized for 1M+ row database with case-insensitive searches

-- Drop tables if they exist (for clean migration)
DROP TABLE IF EXISTS downloads CASCADE;
DROP TABLE IF EXISTS releases CASCADE;
DROP TABLE IF EXISTS releases_archive CASCADE;
DROP TABLE IF EXISTS wishlist CASCADE;

-- Create releases table
CREATE TABLE releases (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    episode TEXT NOT NULL,
    quality TEXT NOT NULL,
    tags TEXT NOT NULL,
    category TEXT NOT NULL,
    date TIMESTAMP,
    link TEXT
);

-- Create releases archive table for old data (>90 days)
CREATE TABLE releases_archive (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    episode TEXT NOT NULL,
    quality TEXT NOT NULL,
    tags TEXT NOT NULL,
    category TEXT NOT NULL,
    date TIMESTAMP,
    link TEXT
);

-- Create downloads table
-- NOTE: No FK constraint to releases since downloads reference releases that may be archived
CREATE TABLE downloads (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    episode TEXT NOT NULL,
    release_id INTEGER  -- Reference only, no FK constraint
);

-- Create wishlist table
CREATE TABLE wishlist (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    includeprops TEXT,
    excludeprops TEXT,
    min_episode TEXT
);

-- Performance-critical indexes for 1M+ rows
-- Case-insensitive indexes using LOWER() for fast ILIKE queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_releases_link_lower ON releases(LOWER(link));
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_releases_title_episode_lower ON releases(LOWER(title), LOWER(episode));
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_downloads_title_episode_lower ON downloads(LOWER(title), LOWER(episode));

-- Standard indexes (removed partial index with NOW() - not immutable)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_releases_date ON releases(date);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_downloads_release_id ON downloads(release_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_wishlist_title_lower ON wishlist(LOWER(title));

-- Archive index
CREATE INDEX IF NOT EXISTS idx_releases_archive_date ON releases_archive(date);
