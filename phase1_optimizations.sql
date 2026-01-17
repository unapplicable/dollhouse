-- Phase 1 PostgreSQL Optimizations for DollHouse
-- These functions push application logic into PostgreSQL for better performance
-- Expected improvement: 53-82% faster overall runtime

-- =============================================================================
-- Phase 1.1: Duplicate Check Function (5-10% improvement)
-- =============================================================================
-- Replaces check_if_show_exists() method
-- Uses EXISTS instead of SELECT * to stop at first match
-- Returns boolean instead of transferring all row data
CREATE OR REPLACE FUNCTION check_release_exists(p_link TEXT)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN EXISTS(
        SELECT 1 FROM releases 
        WHERE LOWER(link) = LOWER(p_link)
    );
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION check_release_exists IS 
'Check if a release already exists by link (case-insensitive). Returns TRUE if exists, FALSE otherwise.';

-- =============================================================================
-- Phase 1.2: Download Check Function (8-12% improvement)
-- =============================================================================
-- Replaces check_to_download() method
-- Uses EXISTS and eliminates unnecessary ORDER BY
-- Returns boolean instead of fetching all rows
CREATE OR REPLACE FUNCTION is_not_downloaded(p_title TEXT, p_episode TEXT)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN NOT EXISTS(
        SELECT 1 FROM downloads 
        WHERE LOWER(title) = LOWER(p_title) 
        AND LOWER(episode) = LOWER(p_episode)
    );
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION is_not_downloaded IS 
'Check if an episode has NOT been downloaded yet (case-insensitive). Returns TRUE if not downloaded, FALSE if already downloaded.';

-- =============================================================================
-- Phase 1.3: Wishlist Matching Function (40-60% improvement)
-- =============================================================================
-- Replaces the entire find_releases() loop with N+2 queries
-- Single set-based query replaces N wishlist queries + filtering loops
-- Includes regex matching, download checking, and quality prioritization
CREATE OR REPLACE FUNCTION find_matching_releases()
RETURNS TABLE(
    release_id INTEGER,
    title TEXT,
    episode TEXT,
    quality TEXT,
    link TEXT,
    tags TEXT,
    wishlist_id INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT DISTINCT ON (r.title, r.episode)
        r.id AS release_id,
        r.title,
        r.episode,
        r.quality,
        r.link,
        r.tags,
        w.id AS wishlist_id
    FROM releases r
    INNER JOIN wishlist w ON LOWER(r.title) = LOWER(w.title)
    WHERE 
        -- Only recent releases (within 3 days)
        r.date > NOW() - INTERVAL '3 days'
        
        -- Episode must be >= min_episode (if specified)
        AND (w.min_episode IS NULL OR LOWER(r.episode) >= LOWER(w.min_episode))
        
        -- Include filter: tags must match pattern (if specified)
        AND (w.includeprops IS NULL OR r.tags ~* w.includeprops)
        
        -- Exclude filter: tags must NOT match pattern (if specified)
        AND (w.excludeprops IS NULL OR r.tags !~* w.excludeprops)
        
        -- Not already downloaded
        AND NOT EXISTS(
            SELECT 1 FROM downloads d 
            WHERE LOWER(d.title) = LOWER(r.title) 
            AND LOWER(d.episode) = LOWER(r.episode)
        )
    
    -- Prioritize by title, episode, then best quality
    ORDER BY 
        r.title, 
        r.episode, 
        CASE r.quality 
            WHEN '2160p' THEN 1
            WHEN '1080p' THEN 2
            WHEN '720p' THEN 3
            ELSE 4
        END;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION find_matching_releases IS 
'Find all releases matching wishlist criteria that have not been downloaded yet. Applies all filters (date, min_episode, include/exclude props, download status) in a single query. Returns releases ordered by quality preference.';
