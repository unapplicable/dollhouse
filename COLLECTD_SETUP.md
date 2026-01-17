# Collectd Monitoring Setup for DollHouse

## ⚠️ IMPORTANT: Secure Setup Required

**This monitoring uses a dedicated read-only PostgreSQL user with minimal privileges.**

For detailed security documentation, see: `SECURE_MONITORING_SETUP.md`

## Quick Start (On Production Server)

```bash
# 1. Copy scripts to production server
scp /tmp/dollhouse-postgresql-collectd.conf root@changwang:/tmp/
scp /tmp/create-collectd-db-user.sh root@changwang:/tmp/
scp /tmp/install-dollhouse-monitoring.sh root@changwang:/tmp/
scp /tmp/check-dollhouse-status.sh root@changwang:/tmp/

# 2. Create secure database user (read-only, minimal privileges)
sudo bash /tmp/create-collectd-db-user.sh

# 3. Install monitoring (automatically uses secure credentials)
sudo bash /tmp/install-dollhouse-monitoring.sh

# 4. Verify monitoring is working
sudo bash /tmp/check-dollhouse-status.sh
```

## Security Features

- ✅ **Dedicated user**: `collectd_monitor` (not using dollhouse user)
- ✅ **Read-only access**: Cannot INSERT, UPDATE, or DELETE data
- ✅ **Minimal privileges**: Only SELECT on required tables + stats views
- ✅ **Secure credentials**: Auto-generated 20-char password stored in `/root/.collectd_db_credentials` (600 permissions)
- ✅ **No hardcoded passwords**: Password injected during installation

## What Gets Monitored

### DollHouse-Specific Metrics
- ✅ Function call counts (`check_release_exists`, `is_not_downloaded`, `find_matching_releases`)
- ✅ Function execution times (total and self time)
- ✅ Table row counts (releases, downloads, wishlist)
- ✅ Table storage sizes
- ✅ Recent releases in 3-day window

### PostgreSQL Performance Metrics
- ✅ Cache hit ratio (should be >95%)
- ✅ Buffer cache hits vs disk reads
- ✅ Transaction counts (commits, rollbacks)
- ✅ Tuple operations (inserts, updates, deletes, fetches)
- ✅ Active connections

## Files Created

| File | Location | Purpose |
|------|----------|---------|
| Config | `/tmp/dollhouse-postgresql-collectd.conf` | Collectd PostgreSQL plugin config |
| Installer | `/tmp/install-dollhouse-monitoring.sh` | Automated setup script |
| Status Check | `/tmp/check-dollhouse-status.sh` | Quick health check |
| Documentation | `/vokk/home/lauri/dev/dollhouse/MONITORING.md` | Full monitoring guide |

## Installation Steps (Manual)

If you prefer manual installation:

```bash
# 1. Copy config to collectd directory
sudo cp /tmp/dollhouse-postgresql-collectd.conf /etc/collectd/collectd.conf.d/dollhouse.conf

# 2. Set correct permissions
sudo chmod 644 /etc/collectd/collectd.conf.d/dollhouse.conf

# 3. Test configuration
sudo collectd -t -C /etc/collectd/collectd.conf

# 4. Restart collectd
sudo systemctl restart collectd

# 5. Verify it's running
sudo systemctl status collectd

# 6. Check for data collection (wait 1-2 minutes)
ls -lh /var/lib/collectd/rrd/$(hostname)/postgresql-dollhouse/
```

## Viewing Metrics

### Real-time PostgreSQL Stats

```bash
# Watch function performance in real-time
watch -n 5 'sudo -u postgres psql -d dollhouse -c "
SELECT 
    funcname,
    calls,
    ROUND(total_time::numeric, 2) as total_ms,
    ROUND((total_time / NULLIF(calls, 0))::numeric, 3) as avg_ms
FROM pg_stat_user_functions 
WHERE schemaname = '\''public'\''
ORDER BY funcname;
"'
```

### Collectd Data Files

```bash
# List collected metrics
ls -lh /var/lib/collectd/rrd/changwang/postgresql-dollhouse/

# View recent data (last hour) using rrdtool
rrdtool fetch /var/lib/collectd/rrd/changwang/postgresql-dollhouse/gauge-function_calls-check_release_exists.rrd AVERAGE -s -1h

# Create a performance graph
rrdtool graph /tmp/dollhouse-performance.png \
    --title "DollHouse Function Calls" \
    --start -24h \
    --width 800 --height 400 \
    DEF:check=/var/lib/collectd/rrd/changwang/postgresql-dollhouse/gauge-function_calls-check_release_exists.rrd:value:AVERAGE \
    DEF:find=/var/lib/collectd/rrd/changwang/postgresql-dollhouse/gauge-function_calls-find_matching_releases.rrd:value:AVERAGE \
    LINE1:check#FF0000:"check_release_exists" \
    LINE2:find#0000FF:"find_matching_releases"
```

## Monitoring Checklist

After installation, verify these items:

- [ ] Collectd service is running: `systemctl status collectd`
- [ ] PostgreSQL plugin loaded: `grep LoadPlugin /etc/collectd/collectd.conf.d/dollhouse.conf`
- [ ] Function tracking enabled: `sudo -u postgres psql -d dollhouse -c "SHOW track_functions;"`
- [ ] Functions being called: Check `pg_stat_user_functions` shows calls > 0
- [ ] Data files created: `ls /var/lib/collectd/rrd/changwang/postgresql-dollhouse/`
- [ ] No errors in logs: `journalctl -u collectd -n 50`

## Expected Performance (Reference)

From benchmarks in `PERFORMANCE_RESULTS.md`:

| Function | Before (ms) | After (ms) | Improvement |
|----------|------------|-----------|-------------|
| `check_release_exists` | 0.27 | 0.20 | 25.5% faster |
| `is_not_downloaded` | 0.60 | 0.40 | 33.4% faster |
| `find_matching_releases` | 78.11 | 6.04 | 92.3% faster |

Your production metrics should match the "After" column.

## Troubleshooting

### No data being collected

```bash
# Check if collectd can connect to PostgreSQL
sudo -u postgres psql -d dollhouse -c "SELECT 1;"

# Run collectd in foreground to see errors
sudo systemctl stop collectd
sudo collectd -f -C /etc/collectd/collectd.conf
# Press Ctrl+C after seeing output, then: sudo systemctl start collectd
```

### Authentication errors

Edit the config and update credentials:
```bash
sudo nano /etc/collectd/collectd.conf.d/dollhouse.conf
# Update: User, Password, Host, Port
sudo systemctl restart collectd
```

### Missing metrics

```bash
# Verify queries work manually
sudo -u postgres psql -d dollhouse -c "
SELECT funcname, calls FROM pg_stat_user_functions 
WHERE schemaname = 'public';
"

# If empty, run DollHouse to generate activity
/home/dh/dollhouse.py
```

## Next Steps

1. **Run the installer** on production server
2. **Wait 24 hours** for baseline data collection
3. **Review metrics** using `check-dollhouse-status.sh`
4. **Compare to benchmarks** in `PERFORMANCE_RESULTS.md`
5. **Set up alerting** (optional) if metrics degrade

## Additional Resources

- Full documentation: `/vokk/home/lauri/dev/dollhouse/MONITORING.md`
- Collectd docs: https://collectd.org/documentation/manpages/collectd.conf.5.shtml#plugin_postgresql
- PostgreSQL stats: https://www.postgresql.org/docs/current/monitoring-stats.html
