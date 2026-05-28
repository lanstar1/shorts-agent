"""스크립트 생성 + 조회 API (3단계)"""
import sys
import os
from fastapi import APIRouter
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from db import database
from services.script_generator import generate_script

router = APIRouter(prefix="/api/scripts", tags=["scripts"])


class GenerateReq(BaseModel):
    angle_id: int


@router.post("/generate")
def generate(req: GenerateReq):
    """선택된 앵글 → 25초 스크립트 풀세트 생성 → story_angles.script_data 저장"""
    try:
        angle = database.get_angle(req.angle_id)
        if not angle:
            return {"error": f"angle_id {req.angle_id}를 찾을 수 없습니다."}

        # 연결된 ranked_topic의 조사 데이터 (보조 컨텍스트)
        research_data = None
        topic_id = angle.get("ranked_topic_id")
        if topic_id:
            topic = database.get_ranked_topic(topic_id)
            if topic:
                research_data = database.load_json(topic.get("research_data"))

        result = generate_script(angle, research_data)
        if "error" in result:
            return result

        database.update_angle_script(req.angle_id, result)
        return {"angle_id": req.angle_id, "script": result}
    except Exception as e:
        import traceback
        return {"error": f"스크립트 생성 중 오류: {type(e).__name__}: {e}",
                "trace": traceback.format_exc()[-500:]}


@router.get("/by-angle/{angle_id}")
def by_angle(angle_id: int):
    angle = database.get_angle(angle_id)
    if not angle:
        return {"error": "앵글을 찾을 수 없습니다."}
    return {"angle_id": angle_id, "script": angle.get("script_data")}
