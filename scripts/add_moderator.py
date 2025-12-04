import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.config.settings import settings
from app.services.admin_service import AdminService
from app.models.admin import Admin

TARGET_TELEGRAM_ID = 241568583
ROLE = "moderator"

async def main():
    print(f"Connecting to DB: {settings.database_url}")
    engine = create_async_engine(settings.database_url)
    AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    async with AsyncSessionLocal() as session:
        admin_service = AdminService(session)
        
        # Check if exists
        admin = await admin_service.get_admin_by_telegram_id(TARGET_TELEGRAM_ID)
        
        if admin:
            print(f"Admin {TARGET_TELEGRAM_ID} found. Current role: {admin.role}")
            if admin.role != ROLE:
                print(f"Updating role to {ROLE}...")
                admin.role = ROLE
                await session.commit()
                print("Updated.")
            else:
                print("Role is already correct.")
                
            # If master key is missing (e.g. added via raw SQL), generate one
            if not admin.master_key:
                print("Generating master key...")
                plain_key = admin_service.generate_master_key()
                admin.master_key = admin_service.hash_master_key(plain_key)
                await session.commit()
                print(f"New Master Key: {plain_key}")
                
        else:
            print(f"Creating new admin {TARGET_TELEGRAM_ID} with role {ROLE}...")
            
            # Find a super admin to assign as creator, or None
            creators = await admin_service.list_all_admins()
            creator_id = creators[0].id if creators else None
            
            new_admin, key, error = await admin_service.create_admin(
                telegram_id=TARGET_TELEGRAM_ID,
                role=ROLE,
                created_by=creator_id,
                username="Moderator"
            )
            
            if error:
                print(f"Error: {error}")
            else:
                print(f"Created successfully.")
                print(f"Telegram ID: {TARGET_TELEGRAM_ID}")
                print(f"Role: {ROLE}")
                print(f"Master Key: {key}")
                print("SAVE THIS KEY SECURELY!")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())

