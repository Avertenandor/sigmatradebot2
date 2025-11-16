#!/usr/bin/env python3
"""Aggressively fix encoding for wallet_admin_service.py"""

import sys
from pathlib import Path

def fix_file_encoding_aggressive(filepath):
    """Try multiple encodings to fix file"""
    try:
        with open(filepath, 'rb') as f:
            raw_data = f.read()

        # Try multiple encodings
        encodings = ['utf-16', 'utf-16-le', 'utf-16-be', 'latin-1', 'cp1252', 'utf-8']
        text = None
        used_encoding = None

        for enc in encodings:
            try:
                text = raw_data.decode(enc)
                used_encoding = enc
                print(f"✅ Successfully decoded as {enc}")
                break
            except (UnicodeDecodeError, UnicodeError):
                continue

        if text is None:
            print("❌ Could not decode file with any encoding. Trying to remove null bytes and use UTF-8.")
            # Last resort: remove null bytes and try UTF-8
            clean_data = raw_data.replace(b'\x00', b'')
            try:
                text = clean_data.decode('utf-8', errors='ignore')
                used_encoding = 'utf-8 (with errors ignored)'
            except:
                print("❌ Complete failure. File may be corrupted.")
                return False

        # Remove null characters
        text_clean = text.replace('\x00', '')
        
        # Write as UTF-8
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(text_clean)
        
        print(f"✅ Fixed: converted from {used_encoding} to UTF-8")
        return True

    except FileNotFoundError:
        print(f"❌ Error: File not found at {filepath}")
        return False
    except Exception as e:
        print(f"❌ An unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    target_file = Path(__file__).parent / "app" / "services" / "wallet_admin_service.py"
    if not target_file.exists():
        print(f"❌ File not found: {target_file}")
        sys.exit(1)
    
    if fix_file_encoding_aggressive(target_file):
        print("✅ Successfully fixed wallet_admin_service.py")
        sys.exit(0)
    else:
        print("❌ Failed to fix wallet_admin_service.py")
        sys.exit(1)

