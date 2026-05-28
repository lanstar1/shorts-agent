"""
스토리텔링 앵글 생성기 (2단계 핵심)

맥가이버 30편 분석으로 추출한 공식을 Claude에게 적용:
- 제품 설명이 아닌 "이슈/맥락"을 던져 인지부조화 자극
- 3유형 앵글: 기대갭 / 숨겨진 진실 / 시장 충격
- 25초 분량, 질문형 클로징
- 가드레일: 단정 금지, 루머 화법, 개인 비방 금지, 근거 없으면 생성 거부

입력: 주제(keyword) + 조사 데이터(research_data)
출력: 앵글 3개 (JSON)
"""
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

SYSTEM_PROMPT = """당신은 IT/전자제품 유튜브 쇼츠 채널의 콘텐츠 기획자다. 30초 이내 쇼츠로 높은 조회수를 내는 '스토리텔링 앵글'을 설계한다.

[채널 공식 — 실제 인기 영상 30편 분석 기반]
- 제품을 설명하지 않는다. 제품을 둘러싼 "이슈/맥락/변수"를 발굴해 시청자의 인지부조화를 자극한다.
- 25초 분량, 하루 1편 페이스
- 모든 영상은 질문형으로 끝나 댓글을 유도한다 ("~까요?", "~날까요?", "~괜찮을까요?")
- 첫 0~2초에 결론이나 충격적 사실을 먼저 던진다

[3가지 앵글 유형 — 반드시 각 1개씩, 총 3개]
1. expectation_gap (기대갭형): "약속됐던 X → 실제는 Y" 구조. 취소/너프/후회/밀려남
2. hidden_truth (숨겨진 진실형): "믿었던 X → 사실은 Y" 구조. 배신감/폭로
3. market_shock (시장 충격형): "평범한 X → 외부변수(환율/정책/사고/품절)로 Z" 구조

[제목 공식]
- 끝에 "ㄷㄷ" 또는 "...?" 로 마무리
- 50자 이내, 호기심·배신감·충격 자극
- 좋은 예: "슬쩍 바꾼거 들켜버린 갤폴드8.. ㄷㄷ", "개인정보 보호는 애플이라며.. ㄷㄷ", "가격 오류인줄 알았는데 진짜였음.. ㄷㄷ"

[가드레일 — 반드시 준수]
- 제품을 "쓰레기/사지마라"로 단정하지 말 것 → 반드시 질문형으로 여지를 남긴다
- 확정되지 않은 정보는 "~한다는 소식", "~라는데", "루머가 있다" 화법을 쓴다
- 개인 실명 비방 금지 (회사명까지만 거론)
- 조사 자료에 근거가 없는 내용은 지어내지 말 것. 근거가 부족한 앵글 유형은 hook을 보수적으로 작성하되, 3개 유형은 모두 채운다

[출력 형식]
반드시 아래 JSON만 출력한다. 마크다운 펜스(```)나 다른 설명 텍스트를 절대 포함하지 마라.
{
  "angles": [
    {
      "angle_type": "expectation_gap",
      "title": "제목 (끝에 ㄷㄷ 또는 ...?)",
      "hook": "0~2초에 던질 첫 문장",
      "data_points": ["근거/사실 1", "근거/사실 2", "근거/사실 3"],
      "closing_question": "질문형 마지막 문장",
      "source_basis": "이 앵글의 근거가 된 조사 자료 출처 요약"
    }
  ]
}"""


def _build_research_summary(research_data: dict, max_per_source=6):
    """research_data에서 소스별 제목을 추출해 프롬프트용 텍스트로 정리"""
    if not research_data:
        return "(조사 자료 없음 - 일반 상식 기반으로 보수적으로 작성)"
    sources = research_data.get("sources", {})
    lines = []
    labels = {
        "coupang": "쿠팡 판매중 제품/가격",
        "naver_news": "한국 뉴스",
        "naver_blog": "한국 블로그/커뮤니티",
        "hackernews": "글로벌 테크 이슈",
        "reddit": "글로벌 커뮤니티 반응",
    }
    for src, items in sources.items():
        if not items:
            continue
        lines.append(f"\n[{labels.get(src, src)}]")
        for it in items[:max_per_source]:
            title = it.get("title") or it.get("name") or ""
            extra = ""
            if it.get("price"):
                extra = f" ({it['price']:,}원)"
            elif it.get("desc"):
                extra = f" - {it['desc'][:60]}"
            lines.append(f"  - {title[:80]}{extra}")
    # 쿠팡 대표 제품/가격
    if research_data.get("coupang_price"):
        lines.append(f"\n[수익화 제품] {research_data.get('coupang_product','')} ({research_data['coupang_price']:,}원)")
    return "\n".join(lines) if lines else "(조사 자료 없음)"


def generate_angles(keyword: str, research_data: dict = None):
    """
    주제 + 조사 데이터로 3유형 앵글 생성.
    반환: {"angles": [...]} 또는 {"error": ...}
    """
    if not config.ANTHROPIC_API_KEY:
        return {"error": "ANTHROPIC_API_KEY가 설정되지 않았습니다."}

    import anthropic
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    research_summary = _build_research_summary(research_data)
    user_msg = f"""[주제]
{keyword}

[조사 자료]
{research_summary}

위 주제와 조사 자료를 바탕으로 3가지 유형의 스토리텔링 앵글을 JSON으로 생성하라."""

    try:
        msg = client.messages.create(
            model=config.ANTHROPIC_MODEL,
            max_tokens=2500,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        text = "".join(b.text for b in msg.content if hasattr(b, "text"))
    except Exception as e:
        return {"error": f"Claude 호출 실패: {e}"}

    # JSON 파싱 (펜스 제거)
    clean = text.strip()
    if clean.startswith("```"):
        clean = clean.split("```", 2)[1] if "```" in clean else clean
        if clean.startswith("json"):
            clean = clean[4:]
        clean = clean.strip("` \n")
    try:
        parsed = json.loads(clean)
        return parsed
    except Exception as e:
        return {"error": f"JSON 파싱 실패: {e}", "raw": text[:500]}


if __name__ == "__main__":
    # 샘플 조사 데이터로 테스트
    sample = {
        "sources": {
            "hackernews": [
                {"title": "Galaxy S26 Ultra's Privacy Display"},
                {"title": "users complain about the Galaxy S26 making them nauseous"},
            ],
            "naver_news": [
                {"title": "삼성 갤럭시 S26, '완성도 vs 실용성' 선택지... 폴더블 중심 전략 재정렬"},
            ],
        },
        "coupang_product": "삼성전자 갤럭시 S26 Ultra 자급제",
        "coupang_price": 1500000,
    }
    result = generate_angles("갤럭시 S26 울트라", sample)
    print(json.dumps(result, ensure_ascii=False, indent=2))
