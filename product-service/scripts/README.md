# Log Cleanup Scripts

This directory contains scripts for automatically cleaning old log entries from the `log.txt` file.

## Files

- `cleanup_logs.py` - Python script that removes log entries older than 30 days
- `cleanup_logs.sh` - Shell wrapper script for running the cleanup from cron
- `crontab` - Cron configuration file that runs the cleanup daily at 11:59 PM

## How It Works

1. **Cron Job**: A cron job is configured to run daily at 11:59 PM (23:59)
2. **Cleanup Script**: The script reads `log.txt` and removes all log entries older than 30 days
3. **Multi-line Support**: The script properly handles multi-line log entries (like stack traces) by keeping or removing them together

## Manual Execution

You can manually run the cleanup script:

```bash
# From the product-service directory
python3 scripts/cleanup_logs.py

# Or using the shell wrapper
./scripts/cleanup_logs.sh
```

## Configuration

The retention period (30 days) can be changed by modifying the `RETENTION_DAYS` constant in `cleanup_logs.py`.

### Cron Schedule Format

To change the cron schedule, edit the `crontab` file. The cron format consists of 5 time fields followed by the command:

```
┌───────────── minute (0 - 59)
│ ┌───────────── hour (0 - 23)
│ │ ┌───────────── day of month (1 - 31)
│ │ │ ┌───────────── month (1 - 12)
│ │ │ │ ┌───────────── day of week (0 - 6) (Sunday=0 or 7)
│ │ │ │ │
* * * * * command
```

**Special Characters:**
- `*` - Matches any value (e.g., `*` in hour field means "every hour")
- `,` - Separates multiple values (e.g., `1,15,30` means "at 1, 15, and 30")
- `-` - Defines a range (e.g., `1-5` means "1 through 5")
- `/` - Defines step values (e.g., `*/15` means "every 15 minutes")
- `?` - No specific value (used in some cron implementations)

**Examples:**

| Cron Expression | Description |
|----------------|-------------|
| `59 23 * * *` | At 11:59 PM every day (current setting) |
| `0 0 * * *` | At midnight (00:00) every day |
| `0 */6 * * *` | Every 6 hours (00:00, 06:00, 12:00, 18:00) |
| `0 2 * * 0` | At 2:00 AM every Sunday |
| `30 3 1 * *` | At 3:30 AM on the 1st day of every month |
| `0 0 1 1 *` | At midnight on January 1st every year |
| `*/30 * * * *` | Every 30 minutes |
| `0 9-17 * * 1-5` | Every hour from 9 AM to 5 PM, Monday to Friday |
| `0 0,12 * * *` | At midnight and noon every day |
| `15 14 1 * *` | At 2:15 PM on the 1st day of every month |

**Current Setting:**
The cleanup script is configured to run at `59 23 * * *`, which means it executes at 11:59 PM every day, ensuring logs are cleaned at the end of each day.

## Docker Setup

The Dockerfile automatically:
1. Installs cron
2. Makes the scripts executable
3. Sets up the cron job
4. Starts cron service when the container starts

## Log Output

Cron job output is logged to `/tmp/cleanup_logs_cron.log` in the container.

