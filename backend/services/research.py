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
import re
import hmac
import hashlib
import urllib.parse
import requests
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from services.collectors.base import today_kst, match_keyword, to_english

COUPANG_DOMAIN = "https://api-gateway.coupang.com"


# 흔한 IT/전자제품 접미 명사 (붙여쓴 키워드 분리용)
PRODUCT_SUFFIXES = [
    "정품케이스", "맥세이프", "케이스", "보호필름", "강화유리", "액정보호",
    "충전기", "케이블", "거치대", "커버", "어댑터", "마우스패드", "마우스",
    "키보드", "이어폰", "헤드폰", "공유기", "모니터", "스탠드", "그립톡",
]


def _tokenize(keyword):
    """
    키워드를 한글/영문/숫자 덩어리로 분리 + 붙여쓴 제품 접미명사 분리.
    '아이폰17 정품케이스' → [아이폰, 17, 정품, 케이스]
    """
    raw = re.findall(r"[가-힣]+|[a-zA-Z]+|[0-9]+", keyword)
    tokens = []
    for t in raw:
        matched = False
        for suf in PRODUCT_SUFFIXES:
            if t != suf and t.endswith(suf) and len(t) > len(suf):
                tokens.append(t[:-len(suf)].lower())
                tokens.append(suf.lower())
                matched = True
                break
        if not matched:
            tokens.append(t.lower())
    return [t for t in tokens if t]


def _relevance(product_name, tokens):
    """제품명이 검색 토큰을 얼마나 포함하는지 점수화"""
    if not product_name:
        return 0
    name = product_name.replace(" ", "").lower()
    hit = sum(1 for t in tokens if t in name)
    score = hit
    # 모든 토큰 포함 시 보너스
    if tokens and hit == len(tokens):
        score += 2
    # 공식 정품 가산 (Apple/삼성 정품)
    if "정품" in name and ("apple" in name or "삼성" in name or "samsung" in name):
        score += 2
    return score


# ---------- 쿠팡 검색 ----------
def _coupang_auth(method, path):
    dt = datetime.now(timezone.utc).strftime("%y%m%dT%H%M%SZ")
    p = path.split("?")
    msg = dt + method + p[0] + (p[1] if len(p) > 1 else "")
    sig = hmac.new(config.COUPANG_SECRET_KEY.encode(), msg.encode(), hashlib.sha256).hexdigest()
    return (f"CEA algorithm=HmacSHA256, access-key={config.COUPANG_ACCESS_KEY}, "
            f"signed-date={dt}, signature={sig}")


def _coupang_search(keyword, fetch=10, top=5):
    """
    쿠팡 검색 후 관련도 재정렬 + 중복제거.
    fetch개 가져와서 키워드 관련도순으로 정렬, 상위 top개 반환.
    주의: 쿠팡 검색 API의 limit 상한은 10. 11 이상이면 rCode=400 반환.
    """
    if not config.COUPANG_ACCESS_KEY:
        return []
    fetch = min(fetch, 10)  # API 상한 강제
    q = urllib.parse.quote(keyword)
    path = (f"/v2/providers/affiliate_open_api/apis/openapi/v1/products/search"
            f"?keyword={q}&limit={fetch}")
    try:
        r = requests.get(COUPANG_DOMAIN + path,
                         headers={"Authorization": _coupang_auth("GET", path)},
                         timeout=config.HTTP_TIMEOUT)
        r.raise_for_status()
        items = r.json().get("data", {}).get("productData", [])
    except Exception as e:
        print(f"[research] coupang 검색 실패: {e}")
        return []

    tokens = _tokenize(keyword)
    # 중복 제거 (productId 기준, 없으면 이름)
    seen = set()
    deduped = []
    for it in items:
        key = it.get("productId") or it.get("productName")
        if key in seen:
            continue
        seen.add(key)
        deduped.append(it)

    # 관련도 점수 부여 후 정렬 (점수 동률이면 원래 순서 유지)
    scored = [(it, _relevance(it.get("productName", ""), tokens)) for it in deduped]
    scored.sort(key=lambda x: -x[1])

    return [{
        "name": it.get("productName"),
        "price": it.get("productPrice"),
        "url": it.get("productUrl"),       # 제휴 링크 (수익화)
        "is_rocket": it.get("isRocket"),
        "relevance": sc,                   # 관련도 점수 (디버깅/표시용)
    } for it, sc in scored[:top]]


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

    # 대표 수익화 링크 = 관련도 1위 제품 (쿠팡 결과는 이미 관련도순 정렬됨)
    coupang_items = sources["coupang"]
    top_item = coupang_items[0] if coupang_items else None

    return {
        "keyword": keyword,
        "axis": axis,
        "coupang_monetizable": monet,
        "sources": sources,
        "summary": summary,
        "total_sources": total,
        "coupang_link": top_item.get("url") if top_item else None,
        "coupang_price": top_item.get("price") if top_item else None,
        "coupang_product": top_item.get("name") if top_item else None,
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
