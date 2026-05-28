"""
자막 빌더 (4단계)

스크립트 → 자막 세그먼트 → SRT / FCPXML 생성.

세그먼트 입력 구조로 설계 (소스 무관):
  - 지금: 스크립트의 예상 타임코드(scene.time)
  - 나중: Whisper STT 결과로 교체 (정확한 타이밍)

FCPXML: Final Cut Pro 1.10, 9:16 세로(1080x1920) 쇼츠 포맷.
자막은 gap 위 connected title로 배치. 흰색 기본 + 노랑 강조.
"""
import re
import html

FPS = 30  # FCPXML frame base


def parse_time_range(time_str):
    """'0:00-0:02' → (0.0, 2.0). 실패 시 None"""
    if not time_str:
        return None
    m = re.match(r"\s*(\d+):(\d+)\s*-\s*(\d+):(\d+)\s*", time_str)
    if not m:
        return None
    s = int(m.group(1)) * 60 + int(m.group(2))
    e = int(m.group(3)) * 60 + int(m.group(4))
    return (float(s), float(e))


def script_to_segments(script):
    """
    스크립트의 scenes → 자막 세그먼트 리스트.
    각 세그먼트: {start, end, text, headline, emphasis[], emphasis_color}
    """
    segments = []
    scenes = script.get("scenes", [])
    fallback_t = 0.0
    default_dur = (script.get("total_duration_sec", 25)) / max(len(scenes), 1)

    for sc in scenes:
        tr = parse_time_range(sc.get("time", ""))
        if tr:
            start, end = tr
        else:
            start, end = fallback_t, fallback_t + default_dur
        fallback_t = end
        # 캡션 우선, 없으면 나레이션
        text = sc.get("caption") or sc.get("narration") or ""
        segments.append({
            "scene": sc.get("scene"),
            "start": start,
            "end": end,
            "text": text.strip(),
            "headline": (sc.get("headline") or "").strip(),
            "narration": (sc.get("narration") or "").strip(),
            "emphasis": sc.get("emphasis") or [],
            "emphasis_color": sc.get("emphasis_color", "yellow"),
        })
    return segments


# ---------- SRT ----------
def _srt_time(sec):
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int(round((sec - int(sec)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_srt(segments):
    lines = []
    for i, seg in enumerate(segments, 1):
        if not seg["text"]:
            continue
        lines.append(str(i))
        lines.append(f"{_srt_time(seg['start'])} --> {_srt_time(seg['end'])}")
        lines.append(seg["text"])
        lines.append("")
    return "\n".join(lines)


# ---------- FCPXML ----------
COLOR_MAP = {
    "yellow": "1 0.84 0 1",
    "red": "0.9 0.15 0.15 1",
    "white": "1 1 1 1",
}


def _fcp_dur(sec):
    """초 → FCPXML frame 분수 ('Nf' 대신 'N/30s' 형식)"""
    frames = int(round(sec * FPS))
    return f"{frames}/{FPS}s"


def _esc(s):
    return html.escape(s or "", quote=True)


def build_fcpxml(segments, project_name="shorts-agent", total_sec=25,
                 font="AppleSDGothicNeo-Bold", base_size=200, headline_size=260):
    """
    세그먼트 → FCPXML 1.11 (9:16 1080x1920), FCP 11.x 호환.
    text-style-def를 title 내부에 두되 textStyleID로 연결.
    title 안에 <text>+<text-style ref>, 같은 title 안에 <text-style-def id> 동봉.
    위치는 Transform의 position 파라미터로 (Basic Title 표준 키).
    """
    total_dur = _fcp_dur(total_sec)
    titles_xml = []
    ts_id = 1

    for seg in segments:
        off = _fcp_dur(seg["start"])
        dur = _fcp_dur(max(seg["end"] - seg["start"], 0.5))

        # 캡션 (lane 1, 하단)
        if seg["text"]:
            ts_main = f"ts{ts_id}"; ts_id += 1
            titles_xml.append(f"""        <title ref="r2" lane="1" offset="{off}" duration="{dur}" name="cap-{seg.get('scene')}" start="0s">
          <param name="Position" key="9999/10199/10201/1/100/101" value="0 -550"/>
          <param name="Alignment" key="9999/10199/10201/2/354/1002961760/401" value="1 (Center)"/>
          <text>
            <text-style ref="{ts_main}">{_esc(seg['text'])}</text-style>
          </text>
          <text-style-def id="{ts_main}">
            <text-style font="{font}" fontSize="{base_size}" fontFace="Bold" fontColor="1 1 1 1" bold="1" strokeColor="0 0 0 1" strokeWidth="-12" alignment="center"/>
          </text-style-def>
        </title>""")

        # 헤드라인 (lane 2, 상단 대형) - 있는 경우만
        if seg["headline"]:
            ts_hl = f"ts{ts_id}"; ts_id += 1
            hl_color = COLOR_MAP.get("yellow")
            hl_text = seg["headline"].replace("\\n", "\n")
            titles_xml.append(f"""        <title ref="r2" lane="2" offset="{off}" duration="{dur}" name="hl-{seg.get('scene')}" start="0s">
          <param name="Position" key="9999/10199/10201/1/100/101" value="0 650"/>
          <param name="Alignment" key="9999/10199/10201/2/354/1002961760/401" value="1 (Center)"/>
          <text>
            <text-style ref="{ts_hl}">{_esc(hl_text)}</text-style>
          </text>
          <text-style-def id="{ts_hl}">
            <text-style font="{font}" fontSize="{headline_size}" fontFace="Bold" fontColor="{hl_color}" bold="1" strokeColor="0 0 0 1" strokeWidth="-14" alignment="center"/>
          </text-style-def>
        </title>""")

    titles_block = "\n".join(titles_xml)

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE fcpxml>
<fcpxml version="1.11">
  <resources>
    <format id="r1" name="FFVideoFormat1080x1920p30" frameDuration="1/30s" width="1080" height="1920" colorSpace="1-1-1 (Rec. 709)"/>
    <effect id="r2" name="Basic Title" uid=".../Titles.localized/Bumper:Opener.localized/Basic Title.localized/Basic Title.moti"/>
  </resources>
  <library>
    <event name="shorts-agent">
      <project name="{_esc(project_name)}">
        <sequence format="r1" duration="{total_dur}" tcStart="0s" tcFormat="NDF" audioLayout="stereo" audioRate="48k">
          <spine>
            <gap name="Gap" offset="0s" duration="{total_dur}" start="0s">
{titles_block}
            </gap>
          </spine>
        </sequence>
      </project>
    </event>
  </library>
</fcpxml>
"""


if __name__ == "__main__":
    sample_script = {
        "title": "테스트", "total_duration_sec": 25,
        "scenes": [
            {"scene": 1, "time": "0:00-0:03", "narration": "갤럭시 폴드8 와이드 이름부터 사라진다는데요",
             "caption": "폴드8 와이드, 이름부터 사라진다", "headline": "폴드8 와이드\n사라진다?",
             "emphasis": ["사라진다"], "emphasis_color": "yellow"},
            {"scene": 2, "time": "0:03-0:06", "narration": "와이드 명칭이 통합될 수 있다는 루머",
             "caption": "그냥 폴드8로 통합?", "headline": "", "emphasis": ["통합"], "emphasis_color": "yellow"},
        ],
    }
    segs = script_to_segments(sample_script)
    print("=== SRT ===")
    print(build_srt(segs))
    print("=== FCPXML (앞부분) ===")
    print(build_fcpxml(segs, "테스트")[:900])
