import asyncio
from app.config.database import async_session_maker
from app.services.finpass_recovery_service import FinpassRecoveryService

async def main():
    async with async_session_maker() as session:
        service = FinpassRecoveryService(session)
        pending = await service.get_all_pending()
        print(f"Pending requests: {len(pending)}")
        for r in pending:
            print(f"- ID: {r.id}, User: {r.user_id}, Status: {r.status}")

if __name__ == "__main__":
    asyncio.run(main())

