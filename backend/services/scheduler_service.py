"""
스케줄러 - 매일 아침 KST 8시 자동 수집
order-agent의 APScheduler 패턴 준수 (Render 슬립 대비 startup check 포함)
"""
import sys
import os
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from services.orchestrator import run_all

KST = timezone(timedelta(hours=9))
_scheduler = None
_last_run = None


def _job():
    global _last_run
    print(f"[scheduler] 정기 수집 시작 {datetime.now(KST)}")
    run_all()
    _last_run = datetime.now(KST)


def start():
    """스케줄러 시작. KST 8시 = UTC 23시(전날)"""
    global _scheduler
    if _scheduler:
        return _scheduler

    _scheduler = BackgroundScheduler(timezone="UTC")
    utc_hour = (config.COLLECT_HOUR_KST - 9) % 24
    _scheduler.add_job(
        _job,
        CronTrigger(hour=utc_hour, minute=0, timezone="UTC"),
        id="daily_collect",
        replace_existing=True,
    )
    _scheduler.start()
    print(f"[scheduler] 시작됨 - 매일 KST {config.COLLECT_HOUR_KST}시 (UTC {utc_hour}시)")
    return _scheduler


def status():
    return {
        "running": _scheduler is not None and _scheduler.running,
        "last_run": _last_run.isoformat() if _last_run else None,
        "collect_hour_kst": config.COLLECT_HOUR_KST,
    }


def run_now():
    """수동 즉시 실행"""
    return run_all()
