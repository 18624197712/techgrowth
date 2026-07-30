import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from .config import Settings, get_settings
from .db import Database
from .services.container import ServiceContainer


def build_scheduler(settings: Settings, services: ServiceContainer) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=settings.timezone)
    radar_task: asyncio.Task | None = None

    async def collect_radar() -> None:
        nonlocal radar_task
        radar_task = asyncio.create_task(services.radar_jobs.run())
        await radar_task

    async def daily_task() -> None:
        if radar_task is not None and not radar_task.done():
            try:
                await asyncio.wait_for(asyncio.shield(radar_task), timeout=120)
            except TimeoutError:
                pass
        if services.growth.has_task_today():
            return
        await services.daily_tasks.generate()
        await services.notifications.dispatch(
            "daily_task",
            "TechGrowth 今日任务已准备",
            f"https://{settings.app_domain}",
        )

    async def weekly_review() -> None:
        item = services.weekly.generate()
        await services.notifications.dispatch(
            "weekly_review",
            "TechGrowth 周复盘已生成",
            f"https://{settings.app_domain}",
            sensitive_body=item.summary,
        )

    async def cleanup_artifacts() -> None:
        removed = services.artifacts.cleanup(services.connector.expired_artifacts())
        services.connector.remove_artifacts(removed)

    scheduler.add_job(
        collect_radar,
        CronTrigger(hour=8, minute=0, timezone=settings.timezone),
        id="collect-radar",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    scheduler.add_job(
        daily_task,
        CronTrigger(hour=8, minute=10, timezone=settings.timezone),
        id="daily-task",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    scheduler.add_job(
        weekly_review,
        CronTrigger(day_of_week="sun", hour=20, minute=0, timezone=settings.timezone),
        id="weekly-review",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    scheduler.add_job(
        cleanup_artifacts,
        IntervalTrigger(hours=1),
        id="cleanup-artifacts",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    return scheduler


async def run_worker() -> None:
    settings = get_settings()
    database = Database(settings.database_url)
    database.create_all()
    services = ServiceContainer.build(database, settings)
    scheduler = build_scheduler(settings, services)
    scheduler.start()
    await asyncio.Event().wait()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
