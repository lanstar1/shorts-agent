"""
Whisper STT 정렬 모듈 (4단계 - 정확한 타이밍)

핵심 전략:
- Whisper로 음성에서 "단어별 타임코드" 추출 (텍스트는 받아쓰기라 부정확)
- 자막 텍스트는 스크립트 캡션을 유지 (이미 정제된 최종본)
- 스크립트 장면별 나레이션 ↔ STT 단어를 매칭 → 각 장면의 실제 start/end 타임코드 산출

매칭 알고리즘:
- 각 장면 나레이션의 앞부분 키워드(앵커)를 STT 단어 시퀀스에서 순차 탐색
- 앵커가 등장하는 시점 = 그 장면의 시작 시각
- 다음 장면 시작 = 현재 장면 끝
"""
import sys
import os
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


def transcribe(audio_path):
    """
    OpenAI Whisper API로 음성 → 단어별 타임코드.
    반환: {"words": [{"word","start","end"}...], "duration": float} 또는 {"error"}
    """
    if not config.OPENAI_API_KEY:
        return {"error": "OPENAI_API_KEY가 설정되지 않았습니다."}

    try:
        from openai import OpenAI
        client = OpenAI(api_key=config.OPENAI_API_KEY)
        with open(audio_path, "rb") as f:
            resp = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                language="ko",
                response_format="verbose_json",
                timestamp_granularities=["word"],
            )
        words = []
        for w in (getattr(resp, "words", None) or []):
            words.append({
                "word": w.get("word") if isinstance(w, dict) else w.word,
                "start": w.get("start") if isinstance(w, dict) else w.start,
                "end": w.get("end") if isinstance(w, dict) else w.end,
            })
        duration = getattr(resp, "duration", None)
        if duration is None and words:
            duration = words[-1]["end"]
        return {"words": words, "duration": duration or 0}
    except Exception as e:
        return {"error": f"Whisper 호출 실패: {e}"}


def _normalize(text):
    """비교용 정규화: 공백/문장부호 제거, 소문자"""
    return re.sub(r"[^가-힣a-z0-9]", "", (text or "").lower())


def _anchor_tokens(narration, n=3):
    """나레이션에서 앵커 토큰 추출 (장면 시작 탐지용). 앞 n개 + 전체 길이 반환"""
    toks = re.findall(r"[가-힣]+|[a-zA-Z]+|[0-9]+", narration or "")
    norm = [_normalize(t) for t in toks if _normalize(t)]
    return norm  # 전체 토큰 반환 (호출측에서 활용)


def _match_anchor(norm_words, search_from, anchors):
    """
    anchors(나레이션 토큰들)의 앞쪽 토큰들이 STT 단어 시퀀스에서
    연속으로 나타나는 시작 위치를 찾는다. 첫 토큰만으로 흔들리지 않게
    최대 3개를 근접 구간(window) 안에서 함께 확인.
    반환: (시작 단어 인덱스, 끝 단어 인덱스) 또는 None
    """
    if not anchors:
        return None
    head = anchors[:3]
    for i in range(search_from, len(norm_words)):
        nw = norm_words[i][0]
        if not (head[0] in nw or nw in head[0]):
            continue
        # 첫 토큰 매칭 → 뒤따르는 head 토큰들이 근처(window=6)에 순서대로 있는지
        matched = 1
        cursor = i + 1
        window_end = min(i + 6, len(norm_words))
        for tok in head[1:]:
            for j in range(cursor, window_end):
                if tok in norm_words[j][0] or norm_words[j][0] in tok:
                    matched += 1
                    cursor = j + 1
                    break
        # head 중 과반 매칭이면 인정 (1개짜리 앵커는 그대로)
        if len(head) == 1 or matched >= max(2, len(head) // 2 + 1):
            return (i, cursor)
    return None


def align_scenes(script, stt_result):
    """
    스크립트 장면 ↔ STT 단어 타임코드 정렬.
    반환: 정렬된 segments 또는 None(폴백)
    """
    words = stt_result.get("words", [])
    duration = stt_result.get("duration", 0)
    scenes = script.get("scenes", [])
    if not words or not scenes:
        return None

    norm_words = [(_normalize(w["word"]), w["start"], w["end"]) for w in words]
    norm_words = [(nw, s, e) for nw, s, e in norm_words if nw]

    scene_starts = []
    search_from = 0

    for sc in scenes:
        narr = sc.get("narration", "")
        anchors = _anchor_tokens(narr)
        match = _match_anchor(norm_words, search_from, anchors)
        if match is not None:
            start_idx, _ = match
            scene_starts.append(norm_words[start_idx][1])
            # 다음 장면 탐색 시작점: 이 장면 나레이션 토큰 수의 약 70%만큼 전진
            # (STT 단어 수 ≈ 나레이션 토큰 수, 겹침 방지를 위해 보수적으로)
            advance = max(1, int(len(anchors) * 0.7))
            search_from = min(start_idx + advance, len(norm_words))
        else:
            scene_starts.append(None)

    scene_starts = _interpolate_starts(scene_starts, duration, len(scenes))

    from services.subtitle_builder import script_to_segments
    base_segs = script_to_segments(script)
    segments = []
    for i, seg in enumerate(base_segs):
        start = scene_starts[i]
        end = scene_starts[i + 1] if i + 1 < len(scene_starts) else duration
        if end <= start:
            end = start + 1.0
        seg["start"] = round(start, 2)
        seg["end"] = round(end, 2)
        segments.append(seg)
    return segments


def _interpolate_starts(starts, duration, n):
    """None인 장면 시작 시각을 앞뒤 기준 선형 보간"""
    result = list(starts)
    # 첫 값이 None이면 0
    if result[0] is None:
        result[0] = 0.0
    # 마지막 보정용
    for i in range(n):
        if result[i] is None:
            # 다음 유효값 찾기
            nxt = None
            for j in range(i + 1, n):
                if result[j] is not None:
                    nxt = j
                    break
            prev_val = result[i - 1] if i > 0 else 0.0
            if nxt is not None:
                step = (result[nxt] - prev_val) / (nxt - (i - 1))
                result[i] = round(prev_val + step, 2)
            else:
                # 이후 전부 None → duration까지 균등 분배
                remaining = n - i
                step = (duration - prev_val) / max(remaining, 1)
                result[i] = round(prev_val + step, 2)
    # 단조 증가 보정
    for i in range(1, n):
        if result[i] <= result[i - 1]:
            result[i] = round(result[i - 1] + 0.3, 2)
    return result


if __name__ == "__main__":
    # 정렬 로직 단위 테스트 (STT 모킹)
    script = {
        "total_duration_sec": 10,
        "scenes": [
            {"scene": 1, "time": "0:00-0:03", "narration": "갤럭시 폴드8 와이드 사라진다는데요", "caption": "폴드8 와이드 사라진다"},
            {"scene": 2, "time": "0:03-0:06", "narration": "와이드 명칭이 통합될 수 있다는 루머", "caption": "그냥 폴드8로 통합?"},
            {"scene": 3, "time": "0:06-0:10", "narration": "울트라 브랜드로 대개편 전망", "caption": "울트라로 통합?"},
        ],
    }
    mock_stt = {
        "duration": 9.5,
        "words": [
            {"word": "갤럭시", "start": 0.2, "end": 0.6},
            {"word": "폴드8", "start": 0.6, "end": 1.1},
            {"word": "와이드", "start": 1.1, "end": 1.5},
            {"word": "사라진다는데요", "start": 1.5, "end": 2.4},
            {"word": "와이드", "start": 3.1, "end": 3.5},
            {"word": "명칭이", "start": 3.5, "end": 4.0},
            {"word": "통합될", "start": 4.0, "end": 4.5},
            {"word": "루머", "start": 4.5, "end": 5.2},
            {"word": "울트라", "start": 6.3, "end": 6.8},
            {"word": "브랜드로", "start": 6.8, "end": 7.4},
            {"word": "대개편", "start": 7.4, "end": 8.2},
        ],
    }
    segs = align_scenes(script, mock_stt)
    print("=== STT 정렬 결과 ===")
    for s in segs:
        print(f"  #{s['scene']} {s['start']}s ~ {s['end']}s | {s['text']}")
