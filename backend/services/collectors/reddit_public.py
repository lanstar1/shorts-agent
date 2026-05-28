"""
레딧 공개 JSON 수집기 (API 키 불필요)
- https://www.reddit.com/r/{sub}/hot.json?limit=N
- User-Agent 헤더만 잘 설정하면 작동 (rate limit ~60req/min)
- 키워드 풀과 매칭되는 핫 포스트만 후보로 채택
"""
import sys
import os
import time
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import config
from services.collectors.base import today_kst, match_keyword_en

# 카테고리별 서브레딧
SUBREDDITS = [
    "apple", "iphone", "ipad",       # 애플 서사
    "samsung", "GalaxyS25", "galaxy", "Android",  # 삼성/안드로이드
    "networking", "HomeNetworking", "buildapc", "hardware",  # 본업
    "gadgets", "headphones",         # 가전/오디오
]


def _fetch_hot(sub, limit=25):
    url = f"https://www.reddit.com/r/{sub}/hot.json?limit={limit}"
    headers = {"User-Agent": config.REDDIT_USER_AGENT}
    r = requests.get(url, headers=headers, timeout=config.HTTP_TIMEOUT)
    if r.status_code != 200:
        return []
    data = r.json()
    return data.get("data", {}).get("children", [])


def collect():
    candidates = []
    date_str = today_kst()
    seen = set()

    for sub in SUBREDDITS:
        try:
            posts = _fetch_hot(sub)
        except Exception as e:
            print(f"[reddit] r/{sub} 실패: {e}")
            continue

        for child in posts:
            p = child.get("data", {})
            title = p.get("title", "")
            if p.get("stickied") or p.get("over_18"):
                continue

            match = match_keyword_en(title)
            if not match:
                continue
            kw, axis, monet = match

            post_id = p.get("id")
            if post_id in seen:
                continue
            seen.add(post_id)

            ups = p.get("ups", 0)
            ratio = p.get("upvote_ratio", 0)
            num_comments = p.get("num_comments", 0)
            # 신호 강도: 업보트 + 댓글 가중 (핫한 정도)
            signal = ups * ratio + num_comments * 2

            candidates.append({
                "collected_date": date_str,
                "source": "reddit",
                "axis": axis,
                "keyword": kw,
                "title": title[:300],
                "signal_type": "hot_post",
                "signal_value": round(signal, 1),
                "url": f"https://reddit.com{p.get('permalink', '')}",
                "raw_data": {
                    "subreddit": sub, "ups": ups, "upvote_ratio": ratio,
                    "num_comments": num_comments,
                },
            })
        time.sleep(1.2)  # rate limit 보호

    print(f"[reddit] 수집 완료: {len(candidates)}건")
    return candidates


if __name__ == "__main__":
    rows = collect()
    for r in sorted(rows, key=lambda x: -x["signal_value"])[:10]:
        print(f"  [{r['axis']}] ({r['signal_value']:.0f}) {r['title'][:60]}")
