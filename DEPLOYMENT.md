# DollHouse Optimization Deployment Guide

## Current Status
- ✅ Code optimized and committed (git commit: latest)
- ✅ All tests passing (19/19)
- ✅ PostgreSQL functions created (`phase1_optimizations.sql`)
- ⏳ **PENDING: Production application restart**

## Expected Performance Improvement
- **92.1% faster** overall query performance
- **12.71x speedup** in release matching
- **83% reduction** in database load

---

## Deployment Steps

### Step 1: Verify PostgreSQL Functions (Optional Check)
Connect to production database and verify functions exist:

```bash
psql -h 10.222.1.22 -U dollhouse -d dollhouse
```

```sql
-- Check if functions exist
\df check_release_exists
\df is_not_downloaded  
\df find_matching_releases

-- If missing, apply them:
\i phase1_optimizations.sql
```

### Step 2: Deploy Code to Production Server
**Where is production?** (Determine based on your setup)
- SSH to production server where DollHouse runs
- Pull latest code from git repository
- Or copy `dollhouse.py` to production location

```bash
# Example (adjust for your setup):
ssh user@production-server
cd /path/to/dollhouse
git pull origin master
# or
scp dollhouse.py user@production-server:/path/to/dollhouse/
```

### Step 3: Restart DollHouse Application
**Method depends on how it's running:**

#### If systemd service:
```bash
sudo systemctl restart dollhouse
sudo systemctl status dollhouse
```

#### If cron job:
```bash
# Just wait for next scheduled run
# Or manually trigger:
python3 /path/to/dollhouse.py
```

#### If manual process:
```bash
# Kill old process
pkill -f dollhouse.py
# Start new process
nohup python3 /path/to/dollhouse.py &
```

### Step 4: Monitor First Run
Check application logs for any errors:

```bash
# Check wherever your logs go
tail -f /var/log/dollhouse.log
# or
journalctl -u dollhouse -f
```

### Step 5: Verify Performance (After 24 Hours)
Connect to database and check function usage statistics:

```sql
SELECT 
    funcname,
    calls,
    round(total_time::numeric, 2) as total_ms,
    round(avg_time::numeric, 3) as avg_ms
FROM pg_stat_user_functions 
WHERE funcname IN ('check_release_exists', 'is_not_downloaded', 'find_matching_releases')
ORDER BY funcname;
```

Expected results:
- `check_release_exists`: ~0.2ms avg (was ~0.27ms)
- `is_not_downloaded`: ~0.4ms avg (was ~0.6ms)
- `find_matching_releases`: ~6ms avg (was ~78ms)

---

## Rollback Plan

If issues occur, rollback is simple:

### Option A: Git Revert
```bash
cd /path/to/dollhouse
git log --oneline -5  # Find commit hash before optimizations
git revert <commit-hash>
# Restart application
```

### Option B: Restore Previous File
```bash
cd /path/to/dollhouse
git checkout HEAD~1 dollhouse.py
# Restart application
```

**Note:** PostgreSQL functions can remain installed - they won't be called by old code.

---

## Troubleshooting

### Error: "function check_release_exists does not exist"
**Cause:** PostgreSQL functions not installed on production database

**Fix:**
```bash
psql -h 10.222.1.22 -U dollhouse -d dollhouse -f phase1_optimizations.sql
```

### Error: "column 'X' does not exist"
**Cause:** Production schema differs from dev

**Fix:** Check production schema matches expected:
```sql
\d releases
\d downloads  
\d wishlist
```

### Performance Not Improved
**Possible causes:**
1. Functions not being called (check with `pg_stat_user_functions`)
2. Missing indexes (verify with `\di`)
3. Database needs VACUUM/ANALYZE: `VACUUM ANALYZE;`

### Application Won't Start
**Check:**
1. Python version compatibility (requires Python 3.x)
2. Database connection string correct
3. Dependencies installed (`pip install -r requirements.txt`)

---

## Post-Deployment

Once deployed successfully:

1. **Monitor for 1 week** - Watch for any unexpected behavior
2. **Collect metrics** - Query `pg_stat_user_functions` to confirm usage
3. **Phase 2 Planning** - If successful, consider additional optimizations:
   - Materialized views for popular queries
   - Connection pooling (PgBouncer)
   - Query result caching

---

## Questions?

If you need help during deployment:
- Check test suite: `pytest test_dollhouse.py -v`
- Review `OPTIMIZATIONS.md` for technical details
- Review `PERFORMANCE_RESULTS.md` for benchmark data
