#!/bin/bash
# Akile Checkin entrypoint - cron-based daily checkin
# Requires: AKILE_ACCOUNTS env var (JSON array)

set -e

echo "Akile Checkin container started"

# Write crontab for daily checkin at 9:00 AM Beijing time (UTC 01:00)
# Also run once at startup (after a 30s delay to let everything settle)
cat > /etc/cron.d/akile-checkin << 'CRON'
SHELL=/bin/bash
PATH=/usr/local/bin:/usr/bin:/bin
TZ=Asia/Shanghai

# Daily checkin at 09:00 Beijing time
0 9 * * * root cd /app && python /app/Akile-Checkin.py >> /var/log/akile-checkin.log 2>&1
CRON

# Create log file
touch /var/log/akile-checkin.log

# Start cron in foreground
echo "Cron jobs:"
cat /etc/cron.d/akile-checkin
echo ""

# Run once on startup (after brief delay)
(sleep 30 && cd /app && python /app/Akile-Checkin.py >> /var/log/akile-checkin.log 2>&1) &

echo "Starting cron daemon..."
exec cron -f -L 15
