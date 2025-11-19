"""
Script to generate master key for existing admin.

Usage:
    python scripts/generate_master_key.py <telegram_id>
    
Example:
    python scripts/generate_master_key.py 1040687384
"""

import asyncio
import sys

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config.settings import settings
from app.repositories.admin_repository import AdminRepository
from app.services.admin_service import AdminService


async def generate_master_key_for_admin(telegram_id: int) -> None:
    """
    Generate and set master key for existing admin.

    Args:
        telegram_id: Telegram ID of the admin
    """
    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        admin_repo = AdminRepository(session)
        admin_service = AdminService(session)

        # Find admin
        admin = await admin_repo.get_by_telegram_id(telegram_id)

        if not admin:
            print(f"❌ Админ с Telegram ID {telegram_id} не найден!")
            return

        print(f"✅ Найден админ: ID={admin.id}, Role={admin.role}, Username=@{admin.username or 'N/A'}")

        # Generate new master key
        plain_master_key = admin_service.generate_master_key()
        hashed_master_key = admin_service.hash_master_key(plain_master_key)

        # Update admin
        admin.master_key = hashed_master_key
        await session.commit()

        print("\n" + "=" * 60)
        print("🔐 МАСТЕР-КЛЮЧ УСПЕШНО СГЕНЕРИРОВАН!")
        print("=" * 60)
        print(f"\nTelegram ID: {telegram_id}")
        print(f"Роль: {admin.role}")
        print(f"Username: @{admin.username or 'N/A'}")
        print("\n" + "-" * 60)
        print("📋 ВАШ МАСТЕР-КЛЮЧ:")
        print("-" * 60)
        print(f"\n{plain_master_key}\n")
        print("-" * 60)
        print("\n⚠️ ВАЖНО:")
        print("• Сохраните этот ключ в безопасном месте")
        print("• Не передавайте его третьим лицам")
        print("• Используйте его для входа в админ-панель")
        print("• При первом входе введите /admin и затем мастер-ключ")
        print("\nДля входа в админ-панель используйте команду /admin")
        print("=" * 60)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/generate_master_key.py <telegram_id>")
        print("Example: python scripts/generate_master_key.py 1040687384")
        sys.exit(1)

    try:
        telegram_id = int(sys.argv[1])
    except ValueError:
        print(f"❌ Неверный Telegram ID: {sys.argv[1]}")
        print("Telegram ID должен быть числом")
        sys.exit(1)

    asyncio.run(generate_master_key_for_admin(telegram_id))

