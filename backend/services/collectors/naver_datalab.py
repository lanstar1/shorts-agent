"""
네이버 데이터랩 검색어 트렌드 수집기
- API: POST https://openapi.naver.com/v1/datalab/search
- 각 키워드의 최근 검색량 추이 → 증가율을 신호로 사용
- order-agent의 NAVER_SEARCH_ID/SECRET 재사용
"""
import sys
import os
import requests
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import config
from data.keyword_pool import KEYWORD_POOL
from services.collectors.base import today_kst

DATALAB_URL = "https://openapi.naver.com/v1/datalab/search"


def _headers():
    return {
        "X-Naver-Client-Id": config.NAVER_SEARCH_ID,
        "X-Naver-Client-Secret": config.NAVER_SEARCH_SECRET,
        "Content-Type": "application/json",
    }


def _trend_for_group(keyword_groups, start, end):
    """데이터랩 API 호출. keyword_groups: [{'groupName':..,'keywords':[..]}] 최대 5개"""
    body = {
        "startDate": start,
        "endDate": end,
        "timeUnit": "date",
        "keywordGroups": keyword_groups,
    }
    r = requests.post(DATALAB_URL, headers=_headers(), json=body, timeout=config.HTTP_TIMEOUT)
    r.raise_for_status()
    return r.json()


def _growth_rate(data_points):
    """최근 7일 평균 vs 직전 7일 평균 증가율 (%)"""
    if not data_points or len(data_points) < 4:
        return 0.0
    ratios = [p["ratio"] for p in data_points]
    half = len(ratios) // 2
    prev = ratios[:half]
    recent = ratios[half:]
    prev_avg = sum(prev) / len(prev) if prev else 0.001
    recent_avg = sum(recent) / len(recent) if recent else 0
    if prev_avg < 0.001:
        prev_avg = 0.001
    return round((recent_avg - prev_avg) / prev_avg * 100, 1)


def collect():
    """
    전체 키워드 풀의 검색 트렌드 수집.
    반환: candidate dict 리스트
    """
    if not config.NAVER_SEARCH_ID:
        print("[naver_datalab] NAVER_SEARCH_ID 없음 - 스킵")
        return []

    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")
    candidates = []
    date_str = today_kst()

    for axis, conf in KEYWORD_POOL.items():
        kws = conf["keywords"]
        # 데이터랩은 그룹당 5개까지, 한 요청에 5그룹까지 → 키워드 1개=1그룹으로 5개씩 배치
        for i in range(0, len(kws), 5):
            batch = kws[i:i + 5]
            groups = [{"groupName": kw, "keywords": [kw]} for kw in batch]
            try:
                resp = _trend_for_group(groups, start, end)
            except Exception as e:
                print(f"[naver_datalab] {axis} batch {i} 실패: {e}")
                continue

            for res in resp.get("results", []):
                kw = res["title"]
                growth = _growth_rate(res.get("data", []))
                # 증가율이 의미있는 것만 (상승 신호)
                if growth <= 5:
                    continue
                candidates.append({
                    "collected_date": date_str,
                    "source": "naver_datalab",
                    "axis": axis,
                    "keyword": kw,
                    "title": f"{kw} 검색 급상승 (+{growth}%)",
                    "signal_type": "search_up",
                    "signal_value": growth,
                    "url": f"https://datalab.naver.com/keyword/trendResult.naver?query={kw}",
                    "raw_data": {"growth_pct": growth, "data": res.get("data", [])[-7:]},
                })
    print(f"[naver_datalab] 수집 완료: {len(candidates)}건")
    return candidates


if __name__ == "__main__":
    rows = collect()
    for r in rows[:10]:
        print(f"  [{r['axis']}] {r['title']}")
