#!/usr/bin/env python3
import os

flag = False

print("=" * 50)
print("Script is running!")
print(f"Current flag value: {flag}")
print("=" * 50)

script_path = os.path.abspath(__file__)

with open(script_path, 'r') as f:
    lines = f.readlines()
    print((type(lines)))
for i, line in enumerate(lines):
    if line.strip().startswith('flag = '):
        if 'True' in line:
            lines[i] = line.replace('True', 'False')
            print("Flag toggled from True to False")
        elif 'False' in line:
            lines[i] = line.replace('False', 'True')
            print("Flag toggled from False to True")
        break

with open(script_path, 'w') as f:
    f.writelines(lines)

print("Script file has been updated!")
print("=" * 50)

