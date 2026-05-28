"""자막 파일 다운로드 API (4단계)"""
import sys
import os
import tempfile
from fastapi import APIRouter, UploadFile, File
from fastapi.responses import Response

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from db import database
from services.subtitle_builder import script_to_segments, build_srt, build_fcpxml

router = APIRouter(prefix="/api/exports", tags=["exports"])


@router.get("/subtitles/{angle_id}.{fmt}")
def download_subtitles(angle_id: int, fmt: str):
    """앵글의 스크립트 → SRT 또는 FCPXML. STT 정렬본 있으면 우선 사용."""
    angle = database.get_angle(angle_id)
    if not angle:
        return Response("앵글을 찾을 수 없습니다.", status_code=404, media_type="text/plain")
    script = angle.get("script_data")
    if not script:
        return Response("먼저 대본을 생성하세요.", status_code=400, media_type="text/plain")

    # STT 정렬본이 있으면 우선, 없으면 스크립트 예상 타임코드
    segments = angle.get("aligned_segments") or script_to_segments(script)
    total = script.get("total_duration_sec", 25)
    if segments:
        total = max(total, max((s["end"] for s in segments), default=total))
    title = script.get("title", "shorts")

    if fmt == "srt":
        content = build_srt(segments)
        media = "application/x-subrip; charset=utf-8"
        filename = f"shorts_{angle_id}.srt"
    elif fmt == "fcpxml":
        content = build_fcpxml(segments, project_name=title, total_sec=total)
        media = "application/xml; charset=utf-8"
        filename = f"shorts_{angle_id}.fcpxml"
    else:
        return Response("지원 형식: srt, fcpxml", status_code=400, media_type="text/plain")

    return Response(
        content.encode("utf-8"),
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/align/{angle_id}")
async def align_with_audio(angle_id: int, audio: UploadFile = File(...)):
    """
    음성 파일 업로드 → Whisper STT → 스크립트 장면과 정렬 → aligned_segments 저장.
    이후 SRT/FCPXML 다운로드 시 정확한 타이밍 적용됨.
    """
    try:
        angle = database.get_angle(angle_id)
        if not angle:
            return {"error": "앵글을 찾을 수 없습니다."}
        script = angle.get("script_data")
        if not script:
            return {"error": "먼저 대본을 생성하세요."}

        # 임시 파일로 저장
        suffix = os.path.splitext(audio.filename or "")[1] or ".m4a"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await audio.read())
            tmp_path = tmp.name

        try:
            from services.stt_aligner import transcribe, align_scenes
            stt = transcribe(tmp_path)
            if "error" in stt:
                return stt
            segments = align_scenes(script, stt)
            if not segments:
                return {"error": "STT 정렬 실패 (음성 인식 결과 부족)"}
            database.update_angle_aligned(angle_id, segments)
            return {
                "angle_id": angle_id,
                "duration": stt.get("duration"),
                "scene_count": len(segments),
                "segments": [{"scene": s["scene"], "start": s["start"],
                              "end": s["end"], "text": s["text"]} for s in segments],
            }
        finally:
            os.unlink(tmp_path)
    except Exception as e:
        import traceback
        return {"error": f"정렬 중 오류: {type(e).__name__}: {e}",
                "trace": traceback.format_exc()[-500:]}
