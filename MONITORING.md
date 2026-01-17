# DollHouse PostgreSQL Monitoring with Collectd

## Overview

This monitoring setup tracks DollHouse PostgreSQL performance using collectd. It monitors:

- **Function performance**: Execution times and call counts for optimized functions
- **Database activity**: Transactions, cache hits, tuple operations
- **Table metrics**: Row counts and storage sizes
- **Performance indicators**: Cache hit ratio, recent releases count

## Installation

### Prerequisites

```bash
# Install collectd if not already installed
sudo apt-get install collectd collectd-core

# Verify PostgreSQL plugin exists
ls -la /usr/lib/x86_64-linux-gnu/collectd/postgresql.so
```

### Quick Install

```bash
# Run the automated setup script
cd /vokk/home/lauri/dev/dollhouse
sudo /tmp/install-dollhouse-monitoring.sh
```

### Manual Install

```bash
# Copy configuration
sudo cp /tmp/dollhouse-postgresql-collectd.conf /etc/collectd/collectd.conf.d/dollhouse.conf

# Test configuration
sudo collectd -t -C /etc/collectd/collectd.conf

# Restart collectd
sudo systemctl restart collectd

# Verify it's running
sudo systemctl status collectd
```

## Metrics Collected

### Function Performance Metrics

| Metric | Description | Type |
|--------|-------------|------|
| `function_calls-check_release_exists` | Number of duplicate check calls | Counter |
| `function_calls-is_not_downloaded` | Number of download check calls | Counter |
| `function_calls-find_matching_releases` | Number of wishlist matching calls | Counter |
| `function_total_time-*` | Total execution time (ms) | Gauge |
| `function_self_time-*` | Self execution time (ms) | Gauge |

### Database Performance Metrics

| Metric | Description | Expected Values |
|--------|-------------|-----------------|
| `cache_hit_ratio` | Buffer cache hit % | >95% is good |
| `blocks_read` | Disk reads | Lower is better |
| `blocks_hit` | Cache hits | Higher is better |
| `connections` | Active connections | Usually 1-2 |

### Application Metrics

| Metric | Description |
|--------|-------------|
| `row_count-releases` | Total releases in database |
| `row_count-downloads` | Total downloads tracked |
| `row_count-wishlist` | Wishlist items count |
| `recent_releases_3day` | Releases in 3-day window |
| `table_size-*` | Table storage size (bytes) |

## Viewing Metrics

### Using RRD Files Directly

Collectd stores data in RRD (Round Robin Database) files:

```bash
# List available metrics
ls -lh /var/lib/collectd/rrd/$(hostname)/postgresql-dollhouse/

# View function call counts (last hour)
rrdtool fetch /var/lib/collectd/rrd/$(hostname)/postgresql-dollhouse/gauge-function_calls-check_release_exists.rrd \
    AVERAGE -s -1h

# Graph function execution times
rrdtool graph /tmp/function-performance.png \
    --title "DollHouse Function Performance" \
    --vertical-label "Time (ms)" \
    --start -24h \
    DEF:check=/var/lib/collectd/rrd/$(hostname)/postgresql-dollhouse/gauge-function_total_time-check_release_exists.rrd:value:AVERAGE \
    DEF:find=/var/lib/collectd/rrd/$(hostname)/postgresql-dollhouse/gauge-function_total_time-find_matching_releases.rrd:value:AVERAGE \
    LINE1:check#FF0000:"check_release_exists" \
    LINE2:find#0000FF:"find_matching_releases"
```

### Using PostgreSQL Directly

Query the source data directly:

```sql
-- Function performance stats
SELECT 
    funcname,
    calls,
    ROUND(total_time::numeric, 2) as total_ms,
    ROUND((total_time / NULLIF(calls, 0))::numeric, 3) as avg_ms,
    ROUND(self_time::numeric, 2) as self_ms
FROM pg_stat_user_functions 
WHERE schemaname = 'public'
ORDER BY total_time DESC;

-- Cache hit ratio
SELECT 
    ROUND(100.0 * blks_hit / NULLIF(blks_hit + blks_read, 0), 2) as cache_hit_ratio_pct,
    blks_hit as cache_hits,
    blks_read as disk_reads
FROM pg_stat_database 
WHERE datname = 'dollhouse';

-- Recent activity summary
SELECT 
    (SELECT COUNT(*) FROM releases) as total_releases,
    (SELECT COUNT(*) FROM downloads) as total_downloads,
    (SELECT COUNT(*) FROM wishlist) as wishlist_items,
    (SELECT COUNT(*) FROM releases WHERE date > NOW() - INTERVAL '3 days') as recent_releases;
```

### Using Grafana (Optional)

If you have Grafana installed, you can visualize collectd metrics:

1. Add data source: `collectd` or `InfluxDB` (if using collectd's write_influxdb plugin)
2. Import dashboard or create custom panels
3. Query metrics using the RRD paths

## Monitoring Commands

### Check Collectd Status

```bash
# Service status
sudo systemctl status collectd

# View logs
sudo journalctl -u collectd -f

# Test configuration
sudo collectd -t -C /etc/collectd/collectd.conf
```

### Reset PostgreSQL Stats

If you want to start fresh:

```sql
-- Reset function stats only
SELECT pg_stat_reset_single_function_counters(oid) 
FROM pg_proc 
WHERE proname IN ('check_release_exists', 'is_not_downloaded', 'find_matching_releases');

-- Reset all database stats
SELECT pg_stat_reset();
```

### Calculate Performance Improvement

After running for a while, compare average execution times:

```sql
-- Current optimized performance
SELECT 
    funcname,
    ROUND((total_time / NULLIF(calls, 0))::numeric, 3) as avg_ms
FROM pg_stat_user_functions 
WHERE funcname IN ('check_release_exists', 'is_not_downloaded', 'find_matching_releases');

-- Compare to benchmarks in PERFORMANCE_RESULTS.md:
-- check_release_exists: 0.27ms → 0.20ms (25.5% faster)
-- is_not_downloaded: 0.60ms → 0.40ms (33.4% faster)  
-- find_matching_releases: 78.11ms → 6.04ms (92.3% faster)
```

## Troubleshooting

### Collectd Not Starting

```bash
# Check logs for errors
sudo journalctl -u collectd -n 50 --no-pager

# Common issues:
# 1. PostgreSQL authentication - check password in config
# 2. Plugin not loaded - verify postgresql.so exists
# 3. Syntax errors - run: sudo collectd -t
```

### No Metrics Being Collected

```bash
# Verify data directory exists
ls -la /var/lib/collectd/rrd/$(hostname)/

# Check if PostgreSQL queries are working
sudo -u postgres psql dollhouse -c "SELECT funcname, calls FROM pg_stat_user_functions;"

# Increase collectd verbosity
sudo systemctl stop collectd
sudo collectd -f -C /etc/collectd/collectd.conf
# Press Ctrl+C after seeing output, then restart normally
```

### PostgreSQL Authentication Failed

If collectd can't connect to PostgreSQL:

```bash
# Test connection manually
psql -h localhost -U dollhouse -d dollhouse -c "SELECT 1;"

# Edit config if needed
sudo nano /etc/collectd/collectd.conf.d/dollhouse.conf
# Update: Host, Port, User, Password

# Restart collectd
sudo systemctl restart collectd
```

## Performance Baselines

After 24 hours of running, you should see approximately:

| Metric | Expected Value | Notes |
|--------|---------------|-------|
| `check_release_exists` calls | ~3,000-5,000/day | ~100 releases/fetch × ~40 fetches/day |
| `find_matching_releases` calls | ~40/day | Once per fetch (every 15-30 min) |
| Average execution times | See PERFORMANCE_RESULTS.md | Should match benchmark |
| Cache hit ratio | >95% | High ratio = good performance |
| Recent releases (3-day) | 800-1,200 | Varies by RSS feed activity |

## Alerting (Optional)

You can set up alerts for performance degradation:

```bash
# Example: Alert if average function time exceeds baseline by 50%
# Using collectd's threshold plugin (add to collectd.conf):

LoadPlugin threshold

<Plugin threshold>
    <Plugin "postgresql">
        Instance "dollhouse"
        <Type "gauge">
            Instance "function_total_time-find_matching_releases"
            WarningMax 9.0     # 6ms × 1.5
            Persist true
        </Type>
    </Plugin>
</Plugin>
```

## Next Steps

1. **Let it run for 24-48 hours** to collect baseline metrics
2. **Check weekly** for performance trends
3. **Compare to benchmarks** in `PERFORMANCE_RESULTS.md`
4. **Monitor cache hit ratio** - should stay >95%
5. **Track database growth** - plan cleanup strategy if needed

## See Also

- `PERFORMANCE_RESULTS.md` - Benchmark data
- `OPTIMIZATIONS.md` - Technical details of optimizations
- `DEPLOYMENT.md` - Deployment guide
- Collectd docs: https://collectd.org/documentation.shtml
- PostgreSQL stats: https://www.postgresql.org/docs/current/monitoring-stats.html
