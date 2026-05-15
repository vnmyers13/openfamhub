from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()


async def start_scheduler():
    scheduler.start()


async def stop_scheduler():
    scheduler.shutdown()
