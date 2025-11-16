#!/usr/bin/env python3
"""Fix encoding for middleware files on server"""

import sys
from pathlib import Path

def fix_file_encoding(filepath):
    """Fix file encoding to UTF-8"""
    try:
        with open(filepath, 'rb') as f:
            raw_data = f.read()

        # Try UTF-16 first (most common issue)
        try:
            text = raw_data.decode('utf-16-le')
            # Remove null bytes and BOM
            text_clean = text.replace('\x00', '').replace('\ufeff', '')
            
            # Write as UTF-8
            with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
                f.write(text_clean)
            print(f"✅ Fixed {filepath}: converted from UTF-16-LE to UTF-8")
            return True
        except (UnicodeDecodeError, UnicodeError):
            pass

        # Try UTF-16-BE
        try:
            text = raw_data.decode('utf-16-be')
            text_clean = text.replace('\x00', '').replace('\ufeff', '')
            
            with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
                f.write(text_clean)
            print(f"✅ Fixed {filepath}: converted from UTF-16-BE to UTF-8")
            return True
        except (UnicodeDecodeError, UnicodeError):
            pass

        # Try UTF-8 with null bytes removal
        try:
            text = raw_data.decode('utf-8')
            text_clean = text.replace('\x00', '')
            
            with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
                f.write(text_clean)
            print(f"✅ Fixed {filepath}: removed null bytes from UTF-8")
            return True
        except (UnicodeDecodeError, UnicodeError):
            pass

        print(f"❌ Could not decode {filepath}")
        return False

    except Exception as e:
        print(f"❌ Error fixing {filepath}: {e}")
        return False

if __name__ == "__main__":
    files = [
        "bot/middlewares/ban_middleware.py",
        "bot/middlewares/logger_middleware.py",
        "bot/middlewares/rate_limit_middleware.py",
        "bot/handlers/__init__.py",
    ]
    
    success = True
    for filepath in files:
        if Path(filepath).exists():
            if not fix_file_encoding(filepath):
                success = False
        else:
            print(f"⚠️  File not found: {filepath}")
    
    sys.exit(0 if success else 1)

