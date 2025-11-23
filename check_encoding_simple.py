#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check encoding of panel.py file."""

import sys

# Read file as bytes
with open("/app/bot/handlers/admin/panel.py", "rb") as f:
    content = f.read()

# Find the line with Админ-панель
lines = content.split(b'\n')
for i, line in enumerate(lines, 1):
    if b'@router.message' in line and (b'\xd0\x90\xd0\xb4\xd0\xbc\xd0\xb8\xd0\xbd' in line or b'Admin' in line):
        print(f"Line {i}: {line[:100]}")
        # Check if it's correct UTF-8
        try:
            decoded = line.decode('utf-8')
            print(f"Decoded OK: {decoded[:80]}")
            if '👑' in decoded and 'Админ-панель' in decoded:
                print("✅ CORRECT: Found emoji and text!")
            else:
                print(f"❌ WRONG: Expected '👑 Админ-панель', got: {decoded[20:60]}")
        except UnicodeDecodeError as e:
            print(f"❌ DECODE ERROR: {e}")

