"""APScheduler integration for scheduled/periodic message broadcasts.

Phase 2: Manages scheduled message execution using APScheduler's
AsyncIOScheduler. Jobs are registered/removed dynamically as teachers
create/cancel scheduled messages.
"""

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="UTC")


def start_scheduler() -> None:
    """Start the scheduler (called during app lifespan startup)."""
    if not scheduler.running:
        scheduler.start()
        logger.info("APScheduler started")


def shutdown_scheduler() -> None:
    """Shut down the scheduler gracefully."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped")


def register_scheduled_job(sm) -> None:
    """Register a ScheduledMessage ORM object as an APScheduler job."""
    job_id = f"scheduled_msg_{sm.id}"

    # Remove existing job if any
    existing = scheduler.get_job(job_id)
    if existing:
        existing.remove()

    if not sm.is_active:
        return

    # Determine trigger
    if sm.schedule_type == "once" and sm.schedule_at:
        trigger = DateTrigger(run_date=sm.schedule_at)
    elif sm.cron_expression:
        parts = sm.cron_expression.split()
        if len(parts) == 5:
            trigger = CronTrigger(
                minute=parts[0],
                hour=parts[1],
                day=parts[2],
                month=parts[3],
                day_of_week=parts[4],
            )
        else:
            logger.warning("Invalid cron expression for scheduled msg %s: %s", sm.id, sm.cron_expression)
            return
    else:
        logger.warning("No trigger config for scheduled msg %s", sm.id)
        return

    scheduler.add_job(
        _execute_scheduled_message,
        trigger=trigger,
        id=job_id,
        args=[sm.id],
        replace_existing=True,
    )
    logger.info("Registered scheduled job %s (type=%s)", job_id, sm.schedule_type)


def remove_scheduled_job(scheduled_id: int) -> None:
    """Remove a scheduled job by its message ID."""
    job_id = f"scheduled_msg_{scheduled_id}"
    job = scheduler.get_job(job_id)
    if job:
        job.remove()
        logger.info("Removed scheduled job %s", job_id)


async def _execute_scheduled_message(scheduled_id: int) -> None:
    """Execute a scheduled message: create a Message row and broadcast via WS."""
    from .database import SessionLocal
    from . import models
    from .ws.manager import manager, message_to_ws_event

    db = SessionLocal()
    try:
        sm = db.get(models.ScheduledMessage, scheduled_id)
        if sm is None or not sm.is_active:
            return

        # Create the actual message
        msg = models.Message(
            teacher_id=sm.teacher_id,
            class_id=sm.class_id,
            content=sm.content,
            display_mode=sm.display_mode,
            reminder_level=sm.reminder_level,
            duration=sm.duration,
            tts_enabled=sm.tts_enabled,
            image_path=sm.image_path,
        )
        db.add(msg)
        db.commit()
        db.refresh(msg)

        logger.info("Executing scheduled message %s -> msg %s", scheduled_id, msg.id)
        await manager.broadcast(msg.class_id, message_to_ws_event(msg))

        # If one-time, deactivate and clean up
        if sm.schedule_type == "once":
            sm.is_active = False
            db.commit()

    except Exception:
        logger.exception("Failed to execute scheduled message %s", scheduled_id)
    finally:
        db.close()


def load_existing_jobs() -> None:
    """Load all active scheduled messages from DB and register them with the scheduler."""
    from .database import SessionLocal
    from . import models

    db = SessionLocal()
    try:
        active = db.query(models.ScheduledMessage).filter_by(is_active=True).all()
        count = 0
        for sm in active:
            try:
                register_scheduled_job(sm)
                count += 1
            except Exception:
                logger.exception("Failed to load scheduled job %s", sm.id)
        if count:
            logger.info("Loaded %d existing scheduled jobs", count)
    finally:
        db.close()
