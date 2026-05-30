"""
스크립트 생성기 (3단계)

선택된 앵글 1개 → 25초 촬영용 스크립트 풀세트 생성:
- 장면별 나레이션 대본 (직접 녹음용)
- 컷 리스트 (맥가이버식 1.2~1.7초 초고속 편집)
- 자막 문구 (헤드라인/캡션 + 강조 키워드 마킹)
- B-roll 가이드 (각 장면에 뭘 보여줄지)
- 효과음 큐

맥가이버 영상기법 분석 기반:
- 25초 평균, 분당 46컷(1.4초/컷), 컷 99% 효과음 동기화
- 상단 헤드라인존 + 중하단 나레이션 자막존
- 흰색(일반) + 노랑(강조) 2색 체계
"""
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

SYSTEM_PROMPT = """당신은 IT 유튜브 쇼츠 영상의 연출/편집 디렉터다. 확정된 스토리텔링 앵글 하나를 받아, 25초 분량의 촬영·편집 스크립트 풀세트를 만든다.

[편집 공식 — 인기 채널 영상기법 정밀분석 기반]
- 총 25초 내외, 8~11개 장면(scene)으로 분해
- 각 장면은 2~3초, 빠른 컷 전환 (초고속 편집 느낌)
- 매 장면 비주얼 소재를 바꿔 시각 자극 유지 (제품렌더 ↔ 실물 ↔ 스크린녹화 ↔ 밈 ↔ 그래픽)
- 모든 컷에 효과음을 붙여 청각 자극 유지 (무음 없음)

[자막 2존 체계]
- 상단 헤드라인존: 첫 1~2개 장면에만, 영상 주제를 던지는 대형 훅 메시지
- 중하단 캡션존: 나레이션을 실시간으로 보여주는 자막 (전 장면)
- 색상: 일반은 흰색, 핵심 데이터/숫자/충격 키워드는 노랑, 가격할인/경고는 빨강

[나레이션 원칙]
- 0~2초에 결론/충격을 먼저 던진다 (제공된 앵글의 hook 활용)
- 본문은 제공된 data_points를 자연스럽게 풀어쓴다
- 마지막은 제공된 closing_question으로 질문하며 끝낸다
- 구어체, 신뢰감 있고 기술적으로 정확하되 비전문가도 이해 가능하게
- 루머는 "~한다는데", "~라는 소식" 화법, 단정 금지

[출력 형식]
반드시 아래 JSON만 출력. 마크다운 펜스(```)나 설명 텍스트 금지.
{
  "title": "영상 제목 (앵글 제목 그대로)",
  "total_duration_sec": 25,
  "scenes": [
    {
      "scene": 1,
      "time": "0:00-0:03",
      "narration": "이 장면에서 말할 나레이션 문장",
      "headline": "상단 대형 훅 자막 (첫 1~2장면만, 없으면 빈 문자열)",
      "caption": "중하단 나레이션 자막 (짧게 축약 가능)",
      "emphasis": ["강조할 키워드1", "강조할 숫자2"],
      "emphasis_color": "yellow",
      "visual": "촬영/B-roll 가이드 (무엇을 어떤 구도로 보여줄지)",
      "broll_type": "제품렌더|실물|스크린녹화|밈|그래픽|인물",
      "sfx": "효과음 큐 (장면 분위기에 맞게 선택). 사용 가능: whoosh(컷전환), impact(충격/북소리 두둥), pop(팝/등장음), ding(띠링/벨), realize(깨달음/정답/마법-아하), coin(돈/가격공개), snap(스냅/포인트), tap(삐빅/장난감)"
    }
  ],
  "production_notes": "전체 촬영/편집 시 주의사항 한두 줄"
}"""


def generate_script(angle: dict, research_data: dict = None):
    """
    앵글 1개 → 25초 스크립트 풀세트.
    angle: {title, hook, data_points, closing_question, angle_type}
    반환: {title, scenes, ...} 또는 {error}
    """
    if not config.ANTHROPIC_API_KEY:
        return {"error": "ANTHROPIC_API_KEY가 설정되지 않았습니다."}

    import anthropic
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    data_points = angle.get("data_points") or []
    dp_text = "\n".join(f"  - {d}" for d in data_points)

    user_msg = f"""[확정된 앵글]
유형: {angle.get('angle_type', '')}
제목: {angle.get('title', '')}
훅(0~2초): {angle.get('hook', '')}
근거 데이터:
{dp_text}
클로징 질문: {angle.get('closing_question', '')}

위 앵글로 25초 촬영·편집 스크립트 풀세트를 JSON으로 생성하라."""

    try:
        msg = client.messages.create(
            model=config.ANTHROPIC_MODEL,
            max_tokens=3000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        text = "".join(b.text for b in msg.content if hasattr(b, "text"))
    except Exception as e:
        return {"error": f"Claude 호출 실패: {e}"}

    clean = text.strip()
    if clean.startswith("```"):
        clean = clean.split("```", 2)[1] if "```" in clean else clean
        if clean.startswith("json"):
            clean = clean[4:]
        clean = clean.strip("` \n")
    try:
        return json.loads(clean)
    except Exception as e:
        return {"error": f"JSON 파싱 실패: {e}", "raw": text[:500]}


if __name__ == "__main__":
    sample_angle = {
        "angle_type": "expectation_gap",
        "title": "와이드 폴드라더니 그냥 폴드8 됐다...?",
        "hook": "갤럭시 Z 폴드8 와이드, 출시 전에 이름부터 사라질 수 있다는데요",
        "data_points": [
            "'갤럭시 Z 폴드8 와이드' 명칭으로 화면 확장형 신모델이 기대됐음",
            "최근 '와이드' 명칭이 사라지고 그냥 '폴드8'로 통합될 수 있다는 루머",
            "고사양 모델에 '울트라' 브랜드를 붙이는 대개편 전망",
        ],
        "closing_question": "와이드 폴드를 기다려온 분들, 그냥 폴드8 하나로 통합돼도 괜찮을까요?",
    }
    result = generate_script(sample_angle)
    print(json.dumps(result, ensure_ascii=False, indent=2))
