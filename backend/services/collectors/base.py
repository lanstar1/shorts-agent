"""수집기 공통 유틸 - 키워드 매칭, 날짜"""
import sys
import os
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from data.keyword_pool import all_keywords  # noqa

KST = timezone(timedelta(hours=9))


def today_kst():
    return datetime.now(KST).strftime("%Y-%m-%d")


# 키워드 → (axis, monetizable) 역인덱스 (소문자 매칭용)
_KW_INDEX = None


def _build_index():
    global _KW_INDEX
    if _KW_INDEX is None:
        _KW_INDEX = []
        for kw, axis, monet in all_keywords():
            _KW_INDEX.append((kw, kw.lower(), axis, monet))
    return _KW_INDEX


def match_keyword(text: str):
    """
    텍스트에서 키워드 풀과 매칭. 영문/한글 모두 부분일치.
    반환: (keyword, axis, monetizable) 또는 None
    가장 긴 키워드 우선 매칭 (구체성 우선).
    """
    if not text:
        return None
    low = text.lower()
    idx = _build_index()
    best = None
    for kw, kw_low, axis, monet in idx:
        # 영문 키워드는 공백 제거 비교도 시도
        if kw_low in low or kw_low.replace(" ", "") in low.replace(" ", ""):
            if best is None or len(kw) > len(best[0]):
                best = (kw, axis, monet)
    return best


# 영문 키워드에 대한 한글↔영문 별칭 (레딧/HN 영문 소스 매칭 강화)
EN_ALIASES = {
    "아이폰17": ["iphone 17"],
    "아이폰17 프로": ["iphone 17 pro"],
    "아이폰 에어": ["iphone air"],
    "아이폰18": ["iphone 18"],
    "폴더블 아이폰": ["foldable iphone", "iphone fold"],
    "맥북 프로 M4": ["macbook pro m4"],
    "맥북 에어 M4": ["macbook air m4"],
    "아이패드 프로 M4": ["ipad pro m4"],
    "에어팟 프로3": ["airpods pro 3"],
    "에어팟4": ["airpods 4"],
    "애플워치 시리즈11": ["apple watch series 11"],
    "iOS 26": ["ios 26"],
    "애플 인텔리전스": ["apple intelligence"],
    "갤럭시 S25": ["galaxy s25"],
    "갤럭시 S25 울트라": ["galaxy s25 ultra"],
    "갤럭시 S26": ["galaxy s26"],
    "갤럭시 폴드7": ["galaxy fold 7", "z fold 7"],
    "갤럭시 폴드8": ["galaxy fold 8", "z fold 8"],
    "갤럭시 플립7": ["galaxy flip 7", "z flip 7"],
    "갤럭시 플립8": ["galaxy flip 8", "z flip 8"],
    "엑시노스": ["exynos"],
    "One UI 8": ["one ui 8", "oneui 8"],
    "Wi-Fi 7 공유기": ["wifi 7", "wi-fi 7", "router wifi 7"],
    "TP-Link 공유기": ["tp-link", "tplink"],
    "ASUS 공유기": ["asus router"],
    "시놀로지 NAS": ["synology", "synology nas"],
    "QNAP NAS": ["qnap"],
    "10G 스위치": ["10gbe switch", "10g switch"],
    "기계식 키보드": ["mechanical keyboard"],
    "게이밍 마우스": ["gaming mouse"],
    "로지텍 마우스": ["logitech mouse"],
    "OLED 모니터": ["oled monitor"],
    "삼성 SSD": ["samsung ssd"],
    "NVMe SSD 2TB": ["nvme ssd", "nvme 2tb"],
    "DDR5 RAM": ["ddr5"],
    "RTX 5070": ["rtx 5070"],
    "RTX 5080": ["rtx 5080"],
    "RTX 5090": ["rtx 5090"],
    "소니 헤드폰": ["sony headphone", "sony wh-1000"],
    "보스 이어폰": ["bose"],
    "다이슨 청소기": ["dyson"],
    "로보락 로봇청소기": ["roborock"],
    "LG OLED TV": ["lg oled"],
}


def match_keyword_en(text: str):
    """영문 소스 전용 매칭 (별칭 사용)"""
    if not text:
        return None
    low = text.lower()
    # 먼저 영문 별칭으로
    for kw, aliases in EN_ALIASES.items():
        for al in aliases:
            if al in low:
                m = match_keyword(kw)
                if m:
                    return m
    # 그다음 일반 매칭
    return match_keyword(text)
