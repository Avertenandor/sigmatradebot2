#!/usr/bin/env python3
"""Fix encoding for wallet_admin_service.py"""

import sys
import chardet
from pathlib import Path

def fix_file_encoding(filepath):
    """Fix file encoding to UTF-8"""
    try:
        with open(filepath, 'rb') as f:
            raw_data = f.read()

        # Detect encoding
        detection = chardet.detect(raw_data)
        encoding = detection['encoding']
        confidence = detection['confidence']

        print(f"Detected encoding: {encoding} (confidence: {confidence:.2f})")

        # Attempt to decode, remove null bytes, and re-encode to UTF-8
        if encoding:
            try:
                # Decode using detected encoding, ignoring errors
                text = raw_data.decode(encoding, errors='ignore')
                # Remove null characters if any
                text_clean = text.replace('\x00', '')
                
                # Re-encode to UTF-8
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(text_clean)
                print(f"✅ Fixed: converted from {encoding} to UTF-8, removed null bytes.")
                return True
            except Exception as e:
                print(f"❌ Error during decode/re-encode: {e}")
                return False
        else:
            print("⚠️ Could not detect encoding. Attempting to remove null bytes directly.")
            # Fallback: remove null bytes directly and assume UTF-8
            clean_data = raw_data.replace(b'\x00', b'')
            with open(filepath, 'wb') as f:
                f.write(clean_data)
            print("✅ Fixed: removed null bytes directly.")
            return True

    except FileNotFoundError:
        print(f"❌ Error: File not found at {filepath}")
        return False
    except Exception as e:
        print(f"❌ An unexpected error occurred: {e}")
        return False

if __name__ == "__main__":
    target_file = Path(__file__).parent / "app" / "services" / "wallet_admin_service.py"
    if not target_file.exists():
        print(f"❌ File not found: {target_file}")
        sys.exit(1)
    
    if fix_file_encoding(target_file):
        print("✅ Successfully fixed wallet_admin_service.py")
        sys.exit(0)
    else:
        print("❌ Failed to fix wallet_admin_service.py")
        sys.exit(1)

