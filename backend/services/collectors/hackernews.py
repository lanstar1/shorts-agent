"""
해커뉴스(Hacker News) 수집기 (API 키 불필요, 무제한)
- topstories.json → 각 item 조회
- IT/테크 이슈 글로벌 최강 소스
- 키워드 매칭되는 스토리만 후보로
"""
import sys
import os
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import config
from services.collectors.base import today_kst, match_keyword_en

HN_BASE = "https://hacker-news.firebaseio.com/v0"


def _top_ids(limit=100):
    r = requests.get(f"{HN_BASE}/topstories.json", timeout=config.HTTP_TIMEOUT)
    r.raise_for_status()
    return r.json()[:limit]


def _item(item_id):
    r = requests.get(f"{HN_BASE}/item/{item_id}.json", timeout=config.HTTP_TIMEOUT)
    if r.status_code != 200:
        return None
    return r.json()


def collect(scan_limit=100):
    candidates = []
    date_str = today_kst()
    try:
        ids = _top_ids(scan_limit)
    except Exception as e:
        print(f"[hackernews] topstories 실패: {e}")
        return []

    for item_id in ids:
        try:
            it = _item(item_id)
        except Exception:
            continue
        if not it or it.get("type") != "story":
            continue
        title = it.get("title", "")
        match = match_keyword_en(title)
        if not match:
            continue
        kw, axis, monet = match

        score = it.get("score", 0)
        descendants = it.get("descendants", 0)  # 댓글 수
        signal = score + descendants * 1.5

        candidates.append({
            "collected_date": date_str,
            "source": "hackernews",
            "axis": axis,
            "keyword": kw,
            "title": title[:300],
            "signal_type": "hot_post",
            "signal_value": round(signal, 1),
            "url": it.get("url") or f"https://news.ycombinator.com/item?id={item_id}",
            "raw_data": {"score": score, "comments": descendants},
        })

    print(f"[hackernews] 수집 완료: {len(candidates)}건")
    return candidates


if __name__ == "__main__":
    rows = collect()
    for r in sorted(rows, key=lambda x: -x["signal_value"])[:10]:
        print(f"  [{r['axis']}] ({r['signal_value']:.0f}) {r['title'][:60]}")
