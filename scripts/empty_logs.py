#!/usr/bin/env python3
import os
from pathlib import Path

def empty_log_files():
    working_dir = Path.cwd()
    
    log_files = list(working_dir.rglob("log.txt"))
    
    if not log_files:
        print("No log.txt files found.")
        return
    
    print(f"Found {len(log_files)} log.txt file(s):")
    
    for log_file in log_files:
        try:
            with open(log_file, 'w') as f:
                pass
            
            relative_path = log_file.relative_to(working_dir)
            print(f"  ✓ Emptied: {relative_path}")
        except Exception as e:
            print(f"  ✗ Error emptying {log_file}: {e}")
    
    print(f"\nCompleted: {len(log_files)} file(s) emptied.")


if __name__ == "__main__":
    empty_log_files()

