# DollHouse Monitoring Web Interface - Setup Guide

## 🎉 Features

✅ **Real-time stats dashboard**
- Function call counts
- Cache hit ratio
- Table row counts
- Recent releases (3-day window)

✅ **Interactive graphs**
- Function performance (calls & execution time)
- Database metrics (cache, transactions)
- Table statistics (rows, sizes)
- Time range selection (1h - 30d)

✅ **Auto-refresh**
- Optional 30-second auto-refresh
- Manual refresh button
- Last update timestamp

✅ **Dark theme**
- Easy on the eyes for long monitoring sessions
- Professional dashboard UI

## 📦 Installation (Production Server)

### Step 1: Copy Files to Production

```bash
# From your dev machine
scp /tmp/index.html root@changwang:/tmp/
scp /tmp/graph.php root@changwang:/tmp/
scp /tmp/install-web-monitoring.sh root@changwang:/tmp/
scp /tmp/disable-veth-monitoring.sh root@changwang:/tmp/
```

### Step 2: Disable veth* Interface Monitoring

```bash
# On production (root@changwang)
sudo bash /tmp/disable-veth-monitoring.sh

# Optional: Remove old veth* RRD files to clean up
find /var/lib/collectd/rrd/changwang/ -type d -name 'interface-veth*' -exec rm -rf {} +
```

### Step 3: Install Web Interface

```bash
# On production (root@changwang)
sudo bash /tmp/install-web-monitoring.sh
```

### Step 4: Access the Dashboard

Open in your browser:
```
https://locals.tf/mon
```

## 🎮 Using the Dashboard

### Main Controls

| Control | Options | Purpose |
|---------|---------|---------|
| **Time Range** | 1h, 3h, 6h, 12h, 24h, 48h, 7d, 30d | Select data time window |
| **Host** | changwang, banana | Switch between monitored hosts |
| **Refresh** | Button | Manually refresh all data |
| **Auto-refresh** | Checkbox | Enable/disable 30-second auto-update |

### Stats Cards (Top Section)

Real-time metrics updated every refresh:

- **Check Calls**: Total `check_release_exists()` function calls
- **Find Calls**: Total `find_matching_releases()` function calls
- **Cache Hit Ratio**: PostgreSQL buffer cache efficiency (should be >95%)
- **Total Releases**: All releases in database
- **Downloads**: Total downloaded episodes
- **Recent (3 days)**: Releases within 3-day processing window

### Graphs (Main Section)

1. **📊 Function Call Counts**
   - Blue: `check_release_exists`
   - Green: `find_matching_releases`
   - Shows activity over time

2. **⚡ Function Execution Time**
   - Orange: `check_release_exists` (should be ~0.2ms)
   - Red: `find_matching_releases` (should be ~6ms)
   - Performance monitoring

3. **🎯 Cache Hit Ratio**
   - Single line showing cache efficiency %
   - Green zone: >95% (optimal)
   - Yellow zone: 90-95% (acceptable)
   - Red zone: <90% (needs attention)

4. **📦 Table Row Counts**
   - Blue: Releases count over time
   - Green: Downloads count
   - Orange: Wishlist size

5. **📈 Recent Releases**
   - Shows releases within 3-day window
   - Indicates current workload

6. **💾 Table Storage Sizes**
   - Stacked area chart
   - Monitors database growth

7. **🔄 Database Transactions**
   - Green area: Commits
   - Red line: Rollbacks
   - Activity indicator

## 🔍 Monitoring Tips

### What to Watch

✅ **Cache Hit Ratio** should stay above 95%
- If dropping: Database needs more memory or VACUUM

✅ **Function execution times** should match benchmarks
- check_release_exists: ~0.2ms average
- find_matching_releases: ~6ms average
- Sudden increases indicate performance issues

✅ **Recent releases (3-day)** shows current load
- Normal: 800-1,200 releases
- High: >1,500 (more work for DollHouse)
- Low: <500 (quiet period)

✅ **Table growth** should be steady
- Releases: Growing slowly over time
- Downloads: Growing with each DollHouse run
- Wishlist: Usually stable

### Performance Baselines

From `PERFORMANCE_RESULTS.md`:

| Metric | Expected Value | Alert If |
|--------|---------------|----------|
| check_release_exists avg | 0.2ms | >0.3ms |
| find_matching_releases avg | 6ms | >10ms |
| Cache hit ratio | >95% | <90% |
| Recent releases | 800-1,200 | >2,000 |

## 🛠️ Troubleshooting

### Dashboard shows "Loading..." forever

**Check:**
```bash
# Verify PHP is working
php -v

# Check web server error logs
tail -f /var/log/nginx/error.log
# or
tail -f /var/log/apache2/error.log

# Test PHP directly
php /var/www/locals.tf/mon/graph.php
```

### Graphs show "Failed to load graph"

**Check:**
```bash
# Verify rrdtool is installed
rrdtool --version

# Check RRD files exist
ls -lh /var/lib/collectd/rrd/changwang/postgresql-dollhouse/

# Test rrdtool manually
rrdtool info /var/lib/collectd/rrd/changwang/postgresql-dollhouse/gauge-function_calls-check_release_exists.rrd

# Check permissions
ls -la /tmp/rrd-cache/
# Should be owned by www-data
```

### Stats show "N/A"

**Possible causes:**
1. Collectd not running: `systemctl status collectd`
2. RRD files not yet created (wait 2-3 minutes after starting collectd)
3. DollHouse hasn't run yet (no data to display)

**Fix:**
```bash
# Run DollHouse to generate activity
/home/dh/dollhouse.py

# Wait 1-2 minutes, then refresh dashboard
```

### PHP errors

**Enable error display:**
```bash
# Edit PHP config
sudo nano /etc/php/8.2/fpm/php.ini  # Adjust version number

# Find and change:
display_errors = On
error_reporting = E_ALL

# Restart PHP-FPM
sudo systemctl restart php8.2-fpm
```

## 📊 Example Queries

### View raw RRD data

```bash
# Last hour of function calls
rrdtool fetch /var/lib/collectd/rrd/changwang/postgresql-dollhouse/gauge-function_calls-check_release_exists.rrd AVERAGE -s -1h

# Get latest value
rrdtool lastupdate /var/lib/collectd/rrd/changwang/postgresql-dollhouse/gauge-cache_hit_ratio.rrd

# RRD file info
rrdtool info /var/lib/collectd/rrd/changwang/postgresql-dollhouse/gauge-function_calls-find_matching_releases.rrd
```

### Manual graph generation

```bash
# Create custom graph
rrdtool graph /tmp/my-graph.png \
    --start -24h \
    --title "My Custom Graph" \
    --width 800 \
    --height 400 \
    DEF:calls=/var/lib/collectd/rrd/changwang/postgresql-dollhouse/gauge-function_calls-check_release_exists.rrd:value:AVERAGE \
    LINE2:calls#3b82f6:"Function Calls"
```

## 🎨 Customization

### Change refresh interval

Edit `/var/www/locals.tf/mon/index.html`:

```javascript
// Find this line:
autoRefreshInterval = setInterval(refreshGraphs, 30000);

// Change 30000 (30 seconds) to desired milliseconds
// Example: 60000 = 1 minute, 10000 = 10 seconds
```

### Add more graphs

Edit `/var/www/locals.tf/mon/graph.php`:

Add to the `handleList()` function:

```php
$graphs[] = ['title' => 'Your Graph Title', 'file' => 'path/to/file.rrd', 'category' => 'custom'];
```

### Change colors

Edit `/var/www/locals.tf/mon/index.html` CSS:

```css
/* Find color definitions */
--color-primary: #3b82f6;    /* Blue */
--color-success: #10b981;    /* Green */
--color-warning: #f59e0b;    /* Orange */
```

## 📁 File Locations

| File | Location | Purpose |
|------|----------|---------|
| Frontend | `/var/www/locals.tf/mon/index.html` | Dashboard UI |
| Backend | `/var/www/locals.tf/mon/graph.php` | Graph generator |
| RRD Data | `/var/lib/collectd/rrd/changwang/` | Time-series data |
| Cache | `/tmp/rrd-cache/` | Generated graphs |
| Collectd Config | `/etc/collectd/collectd.conf.d/` | Monitoring config |

## 🔗 URLs

- **Dashboard**: https://locals.tf/mon
- **API Stats**: https://locals.tf/mon/graph.php?type=stats&host=changwang
- **API List**: https://locals.tf/mon/graph.php?type=list&host=changwang&time=24h
- **Direct Graph**: https://locals.tf/mon/graph.php?type=render&host=changwang&metric=postgresql-dollhouse/function-calls&time=24h

## 📚 See Also

- `MONITORING.md` - Full monitoring documentation
- `SECURE_MONITORING_SETUP.md` - Security setup guide
- `PERFORMANCE_RESULTS.md` - Benchmark data
- RRDtool docs: https://oss.oetiker.ch/rrdtool/doc/index.en.html
