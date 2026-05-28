"""주제 후보 조회 + 수동 수집 트리거 API"""
import sys
import os
from fastapi import APIRouter
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from db import database
from services import scheduler_service

router = APIRouter(prefix="/api/topics", tags=["topics"])
KST = timezone(timedelta(hours=9))


@router.get("/candidates")
def list_candidates(date: str = None, limit: int = 200):
    """수집된 후보 조회 (날짜별)"""
    if not date:
        date = datetime.now(KST).strftime("%Y-%m-%d")
    ph = database._ph()
    with database.get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"""SELECT id, source, axis, keyword, title, signal_type, signal_value, url
                FROM topic_candidates
                WHERE collected_date = {ph}
                ORDER BY signal_value DESC LIMIT {ph}""",
            [date, limit],
        )
        rows = cur.fetchall()
        cur.close()
        cols = ["id", "source", "axis", "keyword", "title", "signal_type", "signal_value", "url"]
        return {"date": date, "count": len(rows),
                "candidates": [dict(zip(cols, r)) for r in rows]}


@router.get("/summary")
def summary(days: int = 5):
    """최근 N일 수집 현황 요약 (소스별/축별 건수)"""
    ph = database._ph()
    with database.get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"""SELECT collected_date, source, axis, COUNT(*) as cnt
                FROM topic_candidates
                GROUP BY collected_date, source, axis
                ORDER BY collected_date DESC"""
        )
        rows = cur.fetchall()
        cur.close()
        result = {}
        for date, source, axis, cnt in rows:
            d = str(date)
            result.setdefault(d, {"by_source": {}, "by_axis": {}, "total": 0})
            result[d]["by_source"][source] = result[d]["by_source"].get(source, 0) + cnt
            result[d]["by_axis"][axis] = result[d]["by_axis"].get(axis, 0) + cnt
            result[d]["total"] += cnt
        return {"summary": result}


@router.post("/collect-now")
def collect_now():
    """수동 즉시 수집 트리거"""
    return scheduler_service.run_now()


@router.get("/scheduler-status")
def scheduler_status():
    return scheduler_service.status()
