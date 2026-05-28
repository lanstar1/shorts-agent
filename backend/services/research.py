"""
On-demand 키워드 조사 모듈 (수동 모드 핵심)

기존 collectors와 차이:
- collectors: 트렌드를 긁어와서 키워드 풀과 "매칭"
- research:   특정 키워드를 각 소스에서 "검색"하여 스토리텔링 소스 수집

5개 소스를 키워드로 검색:
  쿠팡 검색 (제품/가격/할인) — 수익화 링크 확보
  네이버 뉴스 (한국 공식 소식)
  네이버 블로그 (한국 커뮤니티/리뷰 공감대)
  해커뉴스 Algolia (글로벌 이슈/논란)
  레딧 검색 (글로벌 커뮤니티 반응)
"""
import sys
import os
import hmac
import hashlib
import urllib.parse
import requests
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from services.collectors.base import today_kst, match_keyword, to_english

COUPANG_DOMAIN = "https://api-gateway.coupang.com"


# ---------- 쿠팡 검색 ----------
def _coupang_auth(method, path):
    dt = datetime.now(timezone.utc).strftime("%y%m%dT%H%M%SZ")
    p = path.split("?")
    msg = dt + method + p[0] + (p[1] if len(p) > 1 else "")
    sig = hmac.new(config.COUPANG_SECRET_KEY.encode(), msg.encode(), hashlib.sha256).hexdigest()
    return (f"CEA algorithm=HmacSHA256, access-key={config.COUPANG_ACCESS_KEY}, "
            f"signed-date={dt}, signature={sig}")


def _coupang_search(keyword, limit=5):
    if not config.COUPANG_ACCESS_KEY:
        return []
    q = urllib.parse.quote(keyword)
    path = (f"/v2/providers/affiliate_open_api/apis/openapi/v1/products/search"
            f"?keyword={q}&limit={limit}")
    try:
        r = requests.get(COUPANG_DOMAIN + path,
                         headers={"Authorization": _coupang_auth("GET", path)},
                         timeout=config.HTTP_TIMEOUT)
        r.raise_for_status()
        items = r.json().get("data", {}).get("productData", [])
        return [{
            "name": it.get("productName"),
            "price": it.get("productPrice"),
            "url": it.get("productUrl"),  # 제휴 링크 (수익화)
            "is_rocket": it.get("isRocket"),
        } for it in items]
    except Exception as e:
        print(f"[research] coupang 검색 실패: {e}")
        return []


# ---------- 네이버 뉴스/블로그 ----------
def _naver_search(keyword, kind="news", display=8):
    if not config.NAVER_SEARCH_ID:
        return []
    url = f"https://openapi.naver.com/v1/search/{kind}.json"
    headers = {
        "X-Naver-Client-Id": config.NAVER_SEARCH_ID,
        "X-Naver-Client-Secret": config.NAVER_SEARCH_SECRET,
    }
    params = {"query": keyword, "display": display, "sort": "date"}
    try:
        r = requests.get(url, headers=headers, params=params, timeout=config.HTTP_TIMEOUT)
        r.raise_for_status()
        items = r.json().get("items", [])
        def clean(s):
            return (s or "").replace("<b>", "").replace("</b>", "").replace("&quot;", '"').replace("&amp;", "&")
        return [{
            "title": clean(it.get("title")),
            "desc": clean(it.get("description")),
            "url": it.get("link"),
            "date": it.get("pubDate") or it.get("postdate"),
        } for it in items]
    except Exception as e:
        print(f"[research] naver {kind} 실패: {e}")
        return []


# ---------- 해커뉴스 Algolia 검색 ----------
def _hn_search(keyword, limit=8):
    q = urllib.parse.quote(keyword)
    url = f"https://hn.algolia.com/api/v1/search?query={q}&tags=story&hitsPerPage={limit}"
    try:
        r = requests.get(url, timeout=config.HTTP_TIMEOUT)
        r.raise_for_status()
        return [{
            "title": h.get("title"),
            "points": h.get("points"),
            "num_comments": h.get("num_comments"),
            "url": h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}",
        } for h in r.json().get("hits", []) if h.get("title")]
    except Exception as e:
        print(f"[research] hackernews 검색 실패: {e}")
        return []


# ---------- 레딧 검색 ----------
def _reddit_search(keyword, limit=10):
    q = urllib.parse.quote(keyword)
    url = f"https://www.reddit.com/search.json?q={q}&sort=relevance&t=month&limit={limit}"
    try:
        r = requests.get(url, headers={"User-Agent": config.REDDIT_USER_AGENT},
                         timeout=config.HTTP_TIMEOUT)
        if r.status_code != 200:
            return []
        out = []
        for c in r.json().get("data", {}).get("children", []):
            p = c.get("data", {})
            out.append({
                "title": p.get("title"),
                "ups": p.get("ups"),
                "num_comments": p.get("num_comments"),
                "subreddit": p.get("subreddit"),
                "url": f"https://reddit.com{p.get('permalink', '')}",
            })
        return out
    except Exception as e:
        print(f"[research] reddit 검색 실패: {e}")
        return []


def research(keyword: str):
    """
    키워드 1개를 5개 소스에서 조사.
    반환: {keyword, axis, coupang_monetizable, sources{...}, summary{...}}
    """
    match = match_keyword(keyword)
    axis = match[1] if match else "manual"
    monet = match[2] if match else True  # 수동 입력은 대개 수익화 가능 제품

    en_keyword = to_english(keyword)  # 영어 소스용 변환

    sources = {
        "coupang": _coupang_search(keyword),
        "naver_news": _naver_search(keyword, "news"),
        "naver_blog": _naver_search(keyword, "blog"),
        "hackernews": _hn_search(en_keyword),
        "reddit": _reddit_search(en_keyword),
    }

    summary = {k: len(v) for k, v in sources.items()}
    total = sum(summary.values())

    # 쿠팡 최저가/수익화 링크 추출
    coupang_items = sources["coupang"]
    cheapest = None
    if coupang_items:
        valid = [c for c in coupang_items if c.get("price")]
        if valid:
            cheapest = min(valid, key=lambda x: x["price"])

    return {
        "keyword": keyword,
        "axis": axis,
        "coupang_monetizable": monet,
        "sources": sources,
        "summary": summary,
        "total_sources": total,
        "coupang_link": cheapest.get("url") if cheapest else None,
        "coupang_price": cheapest.get("price") if cheapest else None,
        "researched_at": today_kst(),
    }


if __name__ == "__main__":
    import json
    kw = sys.argv[1] if len(sys.argv) > 1 else "갤럭시 S25 울트라"
    result = research(kw)
    print(f"=== '{kw}' 조사 결과 ===")
    print(f"  축: {result['axis']} | 수익화: {result['coupang_monetizable']}")
    print(f"  소스별 수집: {result['summary']} (총 {result['total_sources']}건)")
    if result["coupang_price"]:
        print(f"  쿠팡 최저가: {result['coupang_price']:,}원")
    for src, items in result["sources"].items():
        if items:
            print(f"\n  [{src}]")
            for it in items[:3]:
                t = it.get("title") or it.get("name") or ""
                print(f"    - {t[:60]}")
