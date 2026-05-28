"""
키워드 풀 - 맥가이버 채널 30편 정밀 분석 기반 설계

[분석 핵심 결론]
- 맥가이버는 "제품 카테고리"가 아니라 "브랜드 서사"로 주제를 고른다.
- 애플 22편 / 삼성 18편 (30편 중). 거의 100%가 양강 구도.
- 스마트폰 20편 압도, 태블릿/노트북 각 5, 이어폰 4.
- 하루 1편, 평균 25.7초, 질문형 클로징 83%.

[랜스타 적용 전략 - 4축]
  A. 애플 서사 (35%)  : 트래픽 엔진
  B. 삼성 서사 (30%)  : 트래픽 엔진
  C. 랜스타 본업 (25%): 쿠팡 파트너스 수익 엔진
  D. 빅브랜드 가전(10%): 보강

운영 중 이 파일만 수정하면 즉시 반영됨.
weight = 점수화 시 기본 가중치 (1.0 기준, 본업은 보너스)
"""

# 축별 가중치 (랜스타 수익 전략 반영)
AXIS_WEIGHTS = {
    "apple": 1.0,       # 트래픽
    "samsung": 1.0,     # 트래픽
    "lanstar_core": 1.5,  # 본업 = 쿠팡 수익화 가능 → 보너스
    "appliance": 0.8,   # 보강
}

# 쿠팡 파트너스 수익화 가능 여부 (True면 추가 가중치)
KEYWORD_POOL = {
    # ========== A. 애플 서사 (트래픽 엔진) ==========
    "apple": {
        "coupang_monetizable": True,
        "keywords": [
            # 아이폰 라인업
            "아이폰17", "아이폰17 프로", "아이폰17 프로맥스", "아이폰17e",
            "아이폰 에어", "아이폰18", "폴더블 아이폰",
            # 맥 라인업
            "맥북 프로 M4", "맥북 에어 M4", "맥북 네오", "맥미니 M4",
            # 아이패드
            "아이패드 프로 M4", "아이패드 네오", "아이패드 에어",
            # 오디오/웨어러블
            "에어팟 프로3", "에어팟4", "애플워치 시리즈11",
            # 이슈 추적 키워드 (서사의 핵심)
            "애플 환율", "아이폰 한국 가격", "iOS 26", "애플 인텔리전스",
            "아이폰 사전예약",
        ],
    },

    # ========== B. 삼성 서사 (트래픽 엔진) ==========
    "samsung": {
        "coupang_monetizable": True,
        "keywords": [
            # 갤럭시 S
            "갤럭시 S25", "갤럭시 S25 울트라", "갤럭시 S26",
            # 폴더블
            "갤럭시 폴드7", "갤럭시 폴드8", "갤럭시 플립7", "갤럭시 플립8",
            "갤럭시 와이드 폴드",
            # 탭/워치/버즈
            "갤럭시 탭 S11", "갤럭시 워치8", "갤럭시 버즈4", "갤럭시 링",
            # 이슈 추적 키워드
            "엑시노스", "One UI 8", "갤럭시 7년 업데이트",
            "갤럭시 보상판매", "삼성 갤럭시 판매량",
        ],
    },

    # ========== C. 랜스타 본업 (쿠팡 수익 엔진) ==========
    "lanstar_core": {
        "coupang_monetizable": True,
        "keywords": [
            # 네트워크 (자사 주력)
            "Wi-Fi 7 공유기", "TP-Link 공유기", "ASUS 공유기", "메시 공유기",
            "시놀로지 NAS", "QNAP NAS", "10G 스위치", "PoE 스위치",
            # PC 주변기기
            "기계식 키보드", "무접점 키보드", "게이밍 마우스", "로지텍 마우스",
            "4K 모니터", "OLED 모니터", "게이밍 모니터 240Hz",
            # 저장장치 (가격 변동 큼)
            "삼성 SSD", "NVMe SSD 2TB", "DDR5 RAM",
            # GPU (트렌드 큼)
            "RTX 5070", "RTX 5080", "RTX 5090",
        ],
    },

    # ========== D. 빅브랜드 가전 (보강) ==========
    "appliance": {
        "coupang_monetizable": True,
        "keywords": [
            "소니 헤드폰", "보스 이어폰", "노이즈캔슬링 이어폰",
            "다이슨 청소기", "로보락 로봇청소기",
            "LG OLED TV", "삼성 네오 QLED",
            "미니빔 프로젝터",
        ],
    },
}


def all_keywords():
    """전체 키워드를 (keyword, axis, monetizable) 튜플로 반환"""
    result = []
    for axis, conf in KEYWORD_POOL.items():
        monet = conf.get("coupang_monetizable", False)
        for kw in conf["keywords"]:
            result.append((kw, axis, monet))
    return result


def keyword_count():
    return {axis: len(conf["keywords"]) for axis, conf in KEYWORD_POOL.items()}


if __name__ == "__main__":
    counts = keyword_count()
    total = sum(counts.values())
    print(f"=== 키워드 풀 현황 (총 {total}개) ===")
    for axis, n in counts.items():
        pct = n * 100 // total
        print(f"  {axis:15s}: {n:2d}개 ({pct}%) | weight={AXIS_WEIGHTS[axis]}")
