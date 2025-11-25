
import asyncio
from sqlalchemy import select
from app.db.session import async_session_maker
from app.models.user import User

async def check_users():
    async with async_session_maker() as session:
        # Check Referrer
        referrer_tg_id = 1040687384
        stmt = select(User).where(User.telegram_id == referrer_tg_id)
        result = await session.execute(stmt)
        referrer = result.scalar_one_or_none()
        
        print(f"Referrer (TG={referrer_tg_id}): {referrer}")
        if referrer:
            print(f"  ID: {referrer.id}")
            print(f"  Username: {referrer.username}")

        # Check New User
        new_user_id = 2
        stmt = select(User).where(User.id == new_user_id)
        result = await session.execute(stmt)
        new_user = result.scalar_one_or_none()
        
        print(f"New User (ID={new_user_id}): {new_user}")
        if new_user:
            print(f"  Telegram ID: {new_user.telegram_id}")
            print(f"  Referrer ID: {new_user.referrer_id}")
            
            if new_user.referrer_id:
                # Fetch actual referrer
                stmt = select(User).where(User.id == new_user.referrer_id)
                result = await session.execute(stmt)
                actual_referrer = result.scalar_one_or_none()
                print(f"  Actual Referrer: {actual_referrer}")

if __name__ == "__main__":
    asyncio.run(check_users())

