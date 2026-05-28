"""
쿠팡 파트너스 수집기 (HMAC 인증)
- 골드박스(특가) + 가전디지털 카테고리 베스트
- 할인폭 큰 제품 = 쿠팡 수익화 + 영상 소재 보조 트리거
"""
import sys
import os
import hmac
import hashlib
import requests
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import config
from services.collectors.base import today_kst, match_keyword

DOMAIN = "https://api-gateway.coupang.com"
# 가전디지털 카테고리 (쿠팡 공식: 1016)
CATEGORY_ELECTRONICS = "1016"


def _auth_header(method, url_path):
    """쿠팡 파트너스 HMAC 서명 생성"""
    dt = datetime.now(timezone.utc).strftime("%y%m%dT%H%M%SZ")
    # path와 query 분리
    parts = url_path.split("?")
    path = parts[0]
    query = parts[1] if len(parts) > 1 else ""
    message = dt + method + path + query
    signature = hmac.new(
        config.COUPANG_SECRET_KEY.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return (
        f"CEA algorithm=HmacSHA256, access-key={config.COUPANG_ACCESS_KEY}, "
        f"signed-date={dt}, signature={signature}"
    )


def _get(url_path):
    auth = _auth_header("GET", url_path)
    headers = {"Authorization": auth, "Content-Type": "application/json"}
    r = requests.get(DOMAIN + url_path, headers=headers, timeout=config.HTTP_TIMEOUT)
    r.raise_for_status()
    return r.json()


def collect_goldbox():
    """골드박스(매일 특가) 상품 수집"""
    if not config.COUPANG_ACCESS_KEY:
        print("[coupang] ACCESS_KEY 없음 - 스킵")
        return []
    path = "/v2/providers/affiliate_open_api/apis/openapi/v1/products/goldbox"
    candidates = []
    date_str = today_kst()
    try:
        resp = _get(path)
    except Exception as e:
        print(f"[coupang] goldbox 실패: {e}")
        return []

    for item in resp.get("data", []):
        name = item.get("productName", "")
        match = match_keyword(name)
        # 키워드 매칭 안 돼도 가전 골드박스는 보조 신호로 일부 채택 가능하나,
        # 1주차는 키워드 매칭된 것만 (노이즈 방지)
        if not match:
            continue
        kw, axis, monet = match

        price = item.get("productPrice", 0)
        # 할인율 추정 (골드박스는 보통 할인 큼)
        candidates.append({
            "collected_date": date_str,
            "source": "coupang",
            "axis": axis,
            "keyword": kw,
            "title": name[:300],
            "signal_type": "discount",
            "signal_value": float(price),
            "url": item.get("productUrl", ""),
            "raw_data": {
                "price": price,
                "product_id": item.get("productId"),
                "is_rocket": item.get("isRocket"),
                "category": item.get("categoryName"),
            },
        })
    print(f"[coupang] goldbox 수집: {len(candidates)}건")
    return candidates


def collect_bestcategory(category_id=CATEGORY_ELECTRONICS, limit=50):
    """카테고리 베스트 상품 수집"""
    if not config.COUPANG_ACCESS_KEY:
        return []
    path = (f"/v2/providers/affiliate_open_api/apis/openapi/v1/products/"
            f"bestcategories/{category_id}?limit={limit}")
    candidates = []
    date_str = today_kst()
    try:
        resp = _get(path)
    except Exception as e:
        print(f"[coupang] bestcategory 실패: {e}")
        return []

    for rank, item in enumerate(resp.get("data", []), 1):
        name = item.get("productName", "")
        match = match_keyword(name)
        if not match:
            continue
        kw, axis, monet = match
        candidates.append({
            "collected_date": date_str,
            "source": "coupang",
            "axis": axis,
            "keyword": kw,
            "title": name[:300],
            "signal_type": "rank_up",
            "signal_value": float(limit - rank + 1),  # 순위 역수 = 신호
            "url": item.get("productUrl", ""),
            "raw_data": {
                "rank": rank, "price": item.get("productPrice"),
                "product_id": item.get("productId"),
            },
        })
    print(f"[coupang] bestcategory({category_id}) 수집: {len(candidates)}건")
    return candidates


def collect():
    rows = []
    rows += collect_goldbox()
    rows += collect_bestcategory()
    return rows


if __name__ == "__main__":
    rows = collect()
    for r in rows[:10]:
        print(f"  [{r['axis']}] {r['title'][:60]}")
