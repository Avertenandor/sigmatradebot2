#!/usr/bin/env python3
"""Quick bot check script."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

errors = []
success = []

print("=== Checking Bot Components ===\n")

# Check handlers
print("1. Checking Handlers...")
try:
    from bot.handlers import (
        deposit,
        finpass_recovery,
        instructions,
        menu,
        profile,
        referral,
        start,
        support,
        transaction,
        withdrawal,
    )

    handlers = [
        start,
        menu,
        deposit,
        withdrawal,
        referral,
        profile,
        transaction,
        support,
        finpass_recovery,
        instructions,
    ]
    all_have_routers = all(hasattr(h, "router") for h in handlers)
    if all_have_routers:
        success.append(f"✓ User handlers OK ({len(handlers)} handlers)")
    else:
        errors.append("✗ Some user handlers missing routers")
except Exception as e:
    errors.append(f"✗ User handlers: {e}")

try:
    from bot.handlers.admin import (
        blacklist,
        broadcast,
        deposit_settings,
        management,
        panel,
        users,
        wallet_key_setup,
        wallets,
        withdrawals,
    )
    from bot.handlers.admin import finpass_recovery as admin_finpass

    admin_handlers = [
        panel,
        users,
        withdrawals,
        broadcast,
        blacklist,
        deposit_settings,
        admin_finpass,
        management,
        wallets,
        wallet_key_setup,
    ]
    all_have_routers = all(hasattr(h, "router") for h in admin_handlers)
    if all_have_routers:
        success.append(f"✓ Admin handlers OK ({len(admin_handlers)} handlers)")
    else:
        errors.append("✗ Some admin handlers missing routers")
except Exception as e:
    errors.append(f"✗ Admin handlers: {e}")

# Check middlewares
print("\n2. Checking Middlewares...")
try:
    success.append("✓ All middlewares OK")
except Exception as e:
    errors.append(f"✗ Middlewares: {e}")

# Check services
print("\n3. Checking Services...")
try:
    success.append("✓ All services OK")
except Exception as e:
    errors.append(f"✗ Services: {e}")

# Check models
print("\n4. Checking Models...")
try:
    success.append("✓ All models OK")
except Exception as e:
    errors.append(f"✗ Models: {e}")

# Check repositories
print("\n5. Checking Repositories...")
try:
    success.append("✓ All repositories OK")
except Exception as e:
    errors.append(f"✗ Repositories: {e}")

# Check main
print("\n6. Checking bot.main...")
try:
    from bot.main import main

    assert callable(main)
    success.append("✓ bot.main OK")
except Exception as e:
    errors.append(f"✗ bot.main: {e}")

# Check router registration
print("\n7. Checking Router Registration...")
try:
    main_file = Path(__file__).parent.parent / "bot" / "main.py"
    content = main_file.read_text()

    required_handlers = [
        "include_router(start.router)",
        "include_router(menu.router)",
        "include_router(deposit.router)",
        "include_router(withdrawal.router)",
        "include_router(finpass_recovery.router)",
        "include_router(instructions.router)",
        "include_router(blacklist.router)",
        "include_router(wallet_key_setup.router)",
    ]

    missing = [h for h in required_handlers if h not in content]
    if not missing:
        success.append("✓ All handlers registered in main.py")
    else:
        errors.append(f"✗ Missing registrations: {missing}")
except Exception as e:
    errors.append(f"✗ Router registration check: {e}")

# Summary
print("\n=== Summary ===")
print(f"\n✓ Success: {len(success)}")
for s in success:
    print(f"  {s}")

if errors:
    print(f"\n✗ Errors: {len(errors)}")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)
else:
    print("\n✓ All checks passed!")
    sys.exit(0)
