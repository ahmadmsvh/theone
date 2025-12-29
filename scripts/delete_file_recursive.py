#!/usr/bin/env python3
import os
import argparse
from pathlib import Path

def find_and_delete_files(filename, root_dir='.', dry_run=False):
    root_path = Path(root_dir).resolve()
    deleted_count = 0
    
    if not root_path.exists():
        return 0
    
    for dirpath, dirnames, filenames in os.walk(root_path):
        for file in filenames:
            if file == filename:
                file_path = Path(dirpath) / file
                try:
                    if not dry_run:
                        file_path.unlink()
                    deleted_count += 1
                except:
                    pass
    
    return deleted_count


def main():
    args_parser = argparse.ArgumentParser()
    args_parser.add_argument('filename')
    args_parser.add_argument('--dir', '-d', default='.')
    args_parser.add_argument('--dry-run', action='store_true')
    
    args = args_parser.parse_args()
    find_and_delete_files(args.filename, args.dir, args.dry_run)


if __name__ == '__main__':
    main()
