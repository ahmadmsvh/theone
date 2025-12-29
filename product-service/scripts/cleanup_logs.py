#!/usr/bin/env python3
"""
Log cleanup script for product-service.
Removes log entries older than 30 days from log.txt file.
"""
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Get the service directory (parent of scripts directory)
SERVICE_DIR = Path(__file__).parent.parent
LOG_FILE = SERVICE_DIR / "log.txt"
RETENTION_DAYS = 30


def parse_log_timestamp(line: str) -> datetime | None:
    """
    Parse timestamp from log line.
    Format: YYYY-MM-DD HH:MM:SS - logger_name - LEVEL - message
    """
    try:
        # Extract the timestamp part (first 19 characters: YYYY-MM-DD HH:MM:SS)
        timestamp_str = line[:19]
        return datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
    except (ValueError, IndexError):
        return None


def cleanup_old_logs(log_file: Path, retention_days: int) -> tuple[int, int]:

    if not log_file.exists():
        print(f"Log file not found: {log_file}")
        return 0, 0
    
    cutoff_date = datetime.now() - timedelta(days=retention_days)
    print(f"Cleaning logs older than {cutoff_date.strftime('%Y-%m-%d %H:%M:%S')} (retention: {retention_days} days)")
    
    kept_lines = []
    removed_count = 0
    kept_count = 0
    current_entry_lines = []
    current_entry_timestamp = None
    skip_current_entry = False
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            for line in f:
                # Check if line starts with a timestamp (new log entry)
                if line.strip() and len(line) >= 19 and line[0].isdigit():
                    # Process previous entry
                    if current_entry_timestamp is not None:
                        if not skip_current_entry:
                            kept_lines.extend(current_entry_lines)
                            kept_count += len(current_entry_lines)
                        else:
                            removed_count += len(current_entry_lines)
                    
                    # Start new entry
                    current_entry_lines = [line]
                    current_entry_timestamp = parse_log_timestamp(line)
                    skip_current_entry = (current_entry_timestamp is not None and 
                                         current_entry_timestamp < cutoff_date)
                else:
                    # Continuation line (stack trace, etc.) - add to current entry
                    if current_entry_lines:
                        current_entry_lines.append(line)
                    else:
                        # Orphaned line (shouldn't happen, but keep it to be safe)
                        kept_lines.append(line)
                        kept_count += 1
            
            # Process last entry
            if current_entry_lines:
                if not skip_current_entry:
                    kept_lines.extend(current_entry_lines)
                    kept_count += len(current_entry_lines)
                else:
                    removed_count += len(current_entry_lines)
        
        # Write back the kept lines
        if removed_count > 0:
            with open(log_file, 'w', encoding='utf-8') as f:
                f.writelines(kept_lines)
            print(f"Cleanup complete: Removed {removed_count} old log lines, kept {kept_count} lines")
        else:
            print(f"No old logs to remove. Total lines: {kept_count}")
        
        return kept_count, removed_count
        
    except Exception as e:
        print(f"Error cleaning logs: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    kept, removed = cleanup_old_logs(LOG_FILE, RETENTION_DAYS)
    sys.exit(0)

