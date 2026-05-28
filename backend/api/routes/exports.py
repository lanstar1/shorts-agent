"""자막 파일 다운로드 API (4단계)"""
import sys
import os
from fastapi import APIRouter
from fastapi.responses import Response

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from db import database
from services.subtitle_builder import script_to_segments, build_srt, build_fcpxml

router = APIRouter(prefix="/api/exports", tags=["exports"])


@router.get("/subtitles/{angle_id}.{fmt}")
def download_subtitles(angle_id: int, fmt: str):
    """앵글의 스크립트 → SRT 또는 FCPXML 다운로드"""
    angle = database.get_angle(angle_id)
    if not angle:
        return Response("앵글을 찾을 수 없습니다.", status_code=404, media_type="text/plain")
    script = angle.get("script_data")
    if not script:
        return Response("먼저 대본을 생성하세요.", status_code=400, media_type="text/plain")

    segments = script_to_segments(script)
    total = script.get("total_duration_sec", 25)
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
