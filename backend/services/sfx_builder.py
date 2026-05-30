"""
효과음 합성 엔진 (4단계 - 효과음)

스크립트의 장면별 sfx 큐 → 사용자 SFX 팩에서 파일 매핑 →
각 장면 시작 타임코드 위치에 배치 → 무음 베이스에 합성 → 단일 mp3.

SFX 팩 구조 (사용자가 업로드 후 sfx_pack/ 에 배치):
  backend/data/sfx_pack/
    whoosh.mp3, impact.mp3, pop.mp3, ding.mp3, riser.mp3, ...
파일명 = 큐 종류. 여러 변형이 있으면 whoosh_1.mp3 식으로 두고 랜덤 선택.

ffmpeg 의존: 로컬은 시스템 ffmpeg, Render는 imageio-ffmpeg 폴백.
"""
import os
import sys
import glob
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# SFX 팩 디렉토리
SFX_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "sfx_pack")

# 스크립트가 쓰는 효과음 큐 종류 (script_generator의 sfx 값과 일치)
SFX_TYPES = [
    # 기본 5종
    "whoosh", "impact", "pop", "ding", "riser",
    # 확장 (랜스타 SFX팩 기반)
    "realize", "coin", "snap", "tap",
]

# 큐 별칭 (스크립트가 다른 단어를 쓰면 표준 큐로 매핑)
SFX_ALIASES = {
    "swoosh": "whoosh", "transition": "whoosh", "swipe": "whoosh", "swosh": "whoosh",
    "hit": "impact", "boom": "impact", "bass": "impact", "drum": "impact",
    "ding": "ding", "bell": "ding", "ping": "ding", "ttiring": "ding",
    "pop": "pop", "click": "pop", "blop": "pop",
    "riser": "riser", "rise": "riser", "build": "riser",
    "realize": "realize", "aha": "realize", "insight": "realize",
    "coin": "coin", "money": "coin",
    "snap": "snap", "finger": "snap",
    "tap": "tap", "beep": "tap",
}


def _ensure_ffmpeg():
    """pydub가 쓸 ffmpeg 경로 설정 (Render 폴백 포함)"""
    from pydub import AudioSegment
    import shutil
    if shutil.which("ffmpeg"):
        return True
    try:
        import imageio_ffmpeg
        AudioSegment.converter = imageio_ffmpeg.get_ffmpeg_exe()
        return True
    except Exception:
        return False


def normalize_cue(sfx_cue):
    """스크립트의 sfx 문자열 → 표준 큐 종류. 'whoosh|ding' 같이 여러개면 첫번째."""
    if not sfx_cue:
        return None
    cue = sfx_cue.lower().split("|")[0].split(",")[0].strip()
    # 영문 단어만 추출
    import re
    m = re.search(r"[a-z]+", cue)
    if not m:
        return None
    word = m.group(0)
    return SFX_ALIASES.get(word, word if word in SFX_TYPES else None)


def find_sfx_file(cue):
    """큐 종류 → SFX 팩에서 파일 경로. 변형 여러개면 랜덤. 없으면 None."""
    if not cue:
        return None
    # cue.mp3 또는 cue_*.mp3 (wav도 허용)
    candidates = []
    for ext in ("mp3", "wav", "m4a", "aiff"):
        candidates += glob.glob(os.path.join(SFX_DIR, f"{cue}.{ext}"))
        candidates += glob.glob(os.path.join(SFX_DIR, f"{cue}_*.{ext}"))
    return random.choice(candidates) if candidates else None


def available_sfx():
    """SFX 팩에 있는 큐 종류 목록"""
    if not os.path.isdir(SFX_DIR):
        return []
    found = set()
    audio_exts = (".mp3", ".wav", ".m4a", ".aiff")
    for f in os.listdir(SFX_DIR):
        if f.startswith(".") or not f.lower().endswith(audio_exts):
            continue
        name = os.path.splitext(f)[0].split("_")[0].lower()
        if name:
            found.add(name)
    return sorted(found)


def build_sfx_track(segments, total_sec=25, output_path=None):
    """
    장면 세그먼트 → 효과음이 타임코드에 배치된 단일 mp3.
    각 세그먼트의 start 위치에 해당 sfx를 깐다.
    반환: {output_path, placed:[{scene,cue,time,file}], missing:[큐]} 또는 {error}
    """
    if not _ensure_ffmpeg():
        return {"error": "ffmpeg를 찾을 수 없습니다 (서버에 ffmpeg 또는 imageio-ffmpeg 필요)"}

    from pydub import AudioSegment

    if not os.path.isdir(SFX_DIR) or not os.listdir(SFX_DIR):
        return {"error": "SFX 팩이 비어있습니다. backend/data/sfx_pack/ 에 효과음 파일을 넣으세요.",
                "expected_types": SFX_TYPES}

    # 무음 베이스 트랙 (total_sec, 스테레오 44.1k)
    total_ms = int(total_sec * 1000)
    base = AudioSegment.silent(duration=total_ms, frame_rate=44100)

    placed = []
    missing = []
    for seg in segments:
        cue = normalize_cue(seg.get("sfx"))
        if not cue:
            continue
        sfx_file = find_sfx_file(cue)
        if not sfx_file:
            missing.append(cue)
            continue
        try:
            sound = AudioSegment.from_file(sfx_file)
        except Exception as e:
            missing.append(f"{cue}(로드실패:{e})")
            continue
        pos_ms = int(seg["start"] * 1000)
        base = base.overlay(sound, position=pos_ms)
        placed.append({
            "scene": seg.get("scene"),
            "cue": cue,
            "time": round(seg["start"], 2),
            "file": os.path.basename(sfx_file),
        })

    if output_path is None:
        import tempfile
        output_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3").name

    base.export(output_path, format="mp3", bitrate="192k")
    return {"output_path": output_path, "placed": placed,
            "missing": list(set(missing)), "total_sec": total_sec}


if __name__ == "__main__":
    print("SFX 디렉토리:", SFX_DIR)
    print("사용 가능한 큐:", available_sfx())
    # 큐 정규화 테스트
    for t in ["whoosh", "impact (강)", "ding|pop", "swoosh", "riser", "알수없음"]:
        print(f"  '{t}' → {normalize_cue(t)}")
