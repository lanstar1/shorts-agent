"""
수집 오케스트레이터
4개 소스(네이버/레딧/HN/쿠팡)를 모두 실행하고 topic_candidates에 저장.
스케줄러와 수동 트리거 모두 여기를 호출.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import database
from services.collectors import naver_datalab, reddit_public, hackernews, coupang
from services.collectors.base import today_kst


def run_all():
    """모든 수집기 실행 → DB 저장. 반환: 소스별 건수 dict"""
    database.init_db()
    all_rows = []

    collectors = [
        ("naver_datalab", naver_datalab.collect),
        ("reddit", reddit_public.collect),
        ("hackernews", hackernews.collect),
        ("coupang", coupang.collect),
    ]

    for name, fn in collectors:
        try:
            rows = fn()
            all_rows.extend(rows)
        except Exception as e:
            print(f"[orchestrator] {name} 실패: {e}")

    # DB 저장
    saved = 0
    for row in all_rows:
        try:
            database.insert_candidate(row)
            saved += 1
        except Exception as e:
            print(f"[orchestrator] insert 실패: {e}")

    date_str = today_kst()
    by_source = database.count_candidates_by_date(date_str)
    print(f"[orchestrator] {date_str} 저장 완료: 총 {saved}건 | {by_source}")
    return {"date": date_str, "saved": saved, "by_source": by_source}


if __name__ == "__main__":
    result = run_all()
    print(result)
