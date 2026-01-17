# DollHouse Collectd Monitoring - Secure Setup Guide

## Security Improvements

✅ **Dedicated PostgreSQL user** (`collectd_monitor`)
✅ **Read-only access** (cannot modify data)
✅ **Minimal privileges** (only stats and required tables)
✅ **Secure credentials** (stored in `/root/.collectd_db_credentials` with 600 permissions)
✅ **Automatic password generation** (20-character random password)

## Installation Steps

### Step 1: Create Dedicated Database User

On production server (root@changwang):

```bash
# Create read-only PostgreSQL user for collectd
sudo bash /tmp/create-collectd-db-user.sh
```

This script will:
- Create user `collectd_monitor` with a random secure password
- Grant minimal read-only permissions
- Test the connection and permissions
- Save credentials to `/root/.collectd_db_credentials` (only root can read)
- Verify write operations are blocked

Expected output:
```
=== Creating Collectd PostgreSQL User ===

Creating PostgreSQL user 'collectd_monitor'...
✓ User 'collectd_monitor' created successfully
✓ Credentials saved to: /root/.collectd_db_credentials
✓ Connection test successful
✓ Statistics access granted
✓ Table read access granted
✓ Write operations blocked (as expected)

Credentials:
  Username: collectd_monitor
  Password: <random-20-char-password>
  Database: dollhouse
  Host: localhost
```

### Step 2: Install Collectd Monitoring

```bash
# Install and configure collectd with the secure credentials
sudo bash /tmp/install-dollhouse-monitoring.sh
```

This script will:
- Check prerequisites (collectd, PostgreSQL plugin)
- Load credentials from `/root/.collectd_db_credentials`
- Install collectd configuration with the secure password
- Test configuration validity
- Restart collectd service
- Verify it's working

Expected output:
```
=== DollHouse PostgreSQL Monitoring Setup ===

✓ Found PostgreSQL plugin at: /usr/lib/x86_64-linux-gnu/collectd/postgresql.so
Loading database credentials...
✓ Using database user: collectd_monitor
Installing collectd configuration...
Configuring database credentials...
✓ Installed: /etc/collectd/collectd.conf.d/dollhouse.conf
✓ Configuration is valid
✓ Collectd is running

Metrics are being collected to:
  /var/lib/collectd/rrd/changwang/postgresql-dollhouse/
```

### Step 3: Verify Everything is Working

```bash
# Run comprehensive status check
sudo bash /tmp/check-dollhouse-status.sh
```

Expected output sections:
1. ✅ Database User Status (collectd_monitor connection successful)
2. ✅ PostgreSQL Function Tracking (should show 'all')
3. ✅ Optimized Functions Status (should show 3/3 functions)
4. ✅ Function Performance (shows call counts and execution times)
5. ✅ Collectd Service Status (running, config installed)
6. ✅ Collectd Data Collection (RRD files being created)
7. ✅ Database Overview (row counts)
8. ✅ Database Performance (cache hit ratio)
9. ✅ Last DollHouse Run (recent activity)

## Files Created

### On Production Server

| File | Location | Purpose | Permissions |
|------|----------|---------|-------------|
| Credentials | `/root/.collectd_db_credentials` | Secure password storage | 600 (root only) |
| Collectd Config | `/etc/collectd/collectd.conf.d/dollhouse.conf` | Monitoring configuration | 600 (contains password) |
| RRD Data | `/var/lib/collectd/rrd/changwang/postgresql-dollhouse/` | Time-series metrics | 755 |

### In /tmp (Scripts)

| Script | Purpose |
|--------|---------|
| `create-collectd-db-user.sh` | Creates secure database user |
| `install-dollhouse-monitoring.sh` | Installs and configures collectd |
| `check-dollhouse-status.sh` | Verifies monitoring is working |
| `dollhouse-postgresql-collectd.conf` | Collectd config template |

## Security Features

### PostgreSQL User Permissions

The `collectd_monitor` user has **minimal privileges**:

```sql
-- What collectd_monitor CAN do:
✓ CONNECT to dollhouse database
✓ SELECT from releases, downloads, wishlist tables
✓ Read pg_stat_* views (statistics only, no data)
✓ Execute pg_stat_user_functions (function statistics)

-- What collectd_monitor CANNOT do:
✗ INSERT, UPDATE, DELETE any data
✗ CREATE or DROP tables
✗ Modify schema
✗ Access other databases
✗ Escalate privileges
```

### Password Security

- **Auto-generated**: 20-character random password using OpenSSL
- **Secure storage**: Only readable by root (`chmod 600`)
- **Never in config**: Automatically injected during installation
- **Not logged**: Password not visible in logs or process lists

### File Permissions

```bash
# Credentials file (only root can read)
-rw------- 1 root root  /root/.collectd_db_credentials

# Collectd config (only root can read - contains password)
-rw------- 1 root root  /etc/collectd/collectd.conf.d/dollhouse.conf

# RRD data files (collectd user can write, others can read stats)
drwxr-xr-x collectd collectd /var/lib/collectd/rrd/
```

## Troubleshooting

### User Already Exists

If you need to recreate the user:

```bash
# Drop existing user
sudo -u postgres psql -d dollhouse -c "DROP USER IF EXISTS collectd_monitor;"

# Run creation script again
sudo bash /tmp/create-collectd-db-user.sh
```

### Connection Failed

Check PostgreSQL authentication method:

```bash
# View pg_hba.conf
sudo cat /etc/postgresql/18/main/pg_hba.conf | grep -v "^#" | grep -v "^$"

# Should have a line like:
# host    dollhouse    collectd_monitor    127.0.0.1/32    md5
# or:
# host    all          all                 127.0.0.1/32    scram-sha-256
```

If needed, add:
```bash
# Edit pg_hba.conf
sudo nano /etc/postgresql/18/main/pg_hba.conf

# Add before other rules:
host    dollhouse    collectd_monitor    localhost    md5

# Reload PostgreSQL
sudo systemctl reload postgresql
```

### Permission Denied Errors

Verify user permissions:

```bash
# Load credentials
source /root/.collectd_db_credentials

# Test connection
PGPASSWORD="$COLLECTD_DB_PASSWORD" psql -h localhost -U collectd_monitor -d dollhouse -c "SELECT 1;"

# Test stats access
PGPASSWORD="$COLLECTD_DB_PASSWORD" psql -h localhost -U collectd_monitor -d dollhouse -c "
SELECT funcname, calls FROM pg_stat_user_functions LIMIT 1;
"

# Verify write is blocked (should fail)
PGPASSWORD="$COLLECTD_DB_PASSWORD" psql -h localhost -U collectd_monitor -d dollhouse -c "
DELETE FROM releases WHERE 1=0;
"
# Expected: ERROR: permission denied for table releases
```

### Re-install Monitoring

To start fresh:

```bash
# Stop collectd
sudo systemctl stop collectd

# Remove old config
sudo rm /etc/collectd/collectd.conf.d/dollhouse.conf

# Re-run installer
sudo bash /tmp/install-dollhouse-monitoring.sh

# Check status
sudo bash /tmp/check-dollhouse-status.sh
```

## Viewing Credentials

```bash
# View credentials (root only)
sudo cat /root/.collectd_db_credentials

# Example output:
# COLLECTD_DB_USER=collectd_monitor
# COLLECTD_DB_PASSWORD=AbCdEfGh1234567890Xy
# COLLECTD_DB_HOST=localhost
# COLLECTD_DB_PORT=5432
# COLLECTD_DB_NAME=dollhouse
```

## Monitoring Queries

### Check User Activity

```sql
-- See what collectd_monitor is doing
SELECT 
    usename,
    application_name,
    state,
    query_start,
    LEFT(query, 60) as query
FROM pg_stat_activity 
WHERE usename = 'collectd_monitor';
```

### Verify Permissions

```sql
-- Show granted permissions
SELECT 
    grantee,
    table_schema,
    table_name,
    privilege_type
FROM information_schema.role_table_grants
WHERE grantee = 'collectd_monitor';
```

## Next Steps

After successful installation:

1. ✅ **Wait 10-15 minutes** for initial data collection
2. ✅ **Run status check** to verify metrics are being collected
3. ✅ **Check RRD files** exist and are being updated
4. ✅ **Let it run 24 hours** for baseline metrics
5. ✅ **Compare performance** to benchmarks in `PERFORMANCE_RESULTS.md`

## Performance Baselines

After 24 hours, you should see:

| Metric | Expected Value |
|--------|---------------|
| Function calls | ~3,000-5,000 check_release_exists/day |
| Avg execution time | ~0.2ms for check_release_exists |
| Avg execution time | ~6ms for find_matching_releases |
| Cache hit ratio | >95% |
| Data files | ~15-20 RRD files in collectd directory |

## See Also

- `MONITORING.md` - Full monitoring documentation
- `COLLECTD_SETUP.md` - Collectd setup guide
- `PERFORMANCE_RESULTS.md` - Benchmark data
- `OPTIMIZATIONS.md` - Technical details
