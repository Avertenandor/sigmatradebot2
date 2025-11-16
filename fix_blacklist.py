#!/usr/bin/env python3
"""Fix blacklist_service.py by removing null bytes."""
import sys

file_path = 'app/services/blacklist_service.py'
if len(sys.argv) > 1:
    file_path = sys.argv[1]

with open(file_path, 'rb') as f:
    data = f.read()

clean_data = data.replace(b'\x00', b'')

if len(clean_data) < len(data):
    with open(file_path, 'wb') as f:
        f.write(clean_data)
    print(f"Fixed: removed {len(data) - len(clean_data)} null bytes")
else:
    print("No null bytes found")

