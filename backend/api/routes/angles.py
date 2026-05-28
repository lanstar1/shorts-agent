"""스토리텔링 앵글 생성 + 조회 API"""
import sys
import os
from fastapi import APIRouter
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from db import database
from services.angle_generator import generate_angles

router = APIRouter(prefix="/api/angles", tags=["angles"])
KST = timezone(timedelta(hours=9))


class GenerateReq(BaseModel):
    topic_id: int


@router.post("/generate")
def generate(req: GenerateReq):
    """
    ranked_topic(자동/수동)을 받아 앵글 3개 생성 → story_angles 저장.
    """
    topic = database.get_ranked_topic(req.topic_id)
    if not topic:
        return {"error": f"topic_id {req.topic_id}를 찾을 수 없습니다."}

    keyword = topic.get("keyword") or topic.get("title")
    research_data = database.load_json(topic.get("research_data"))

    result = generate_angles(keyword, research_data)
    if "error" in result:
        return result

    angles = result.get("angles", [])
    date_str = datetime.now(KST).strftime("%Y-%m-%d")
    saved = []
    for a in angles:
        angle_id = database.insert_story_angle({
            "ranked_topic_id": req.topic_id,
            "generated_date": date_str,
            "angle_type": a.get("angle_type"),
            "title": a.get("title"),
            "hook": a.get("hook"),
            "data_points": a.get("data_points"),
            "closing_question": a.get("closing_question"),
            "curation_score": 0,
        })
        a["id"] = angle_id
        saved.append(a)

    # topic 상태 업데이트
    _update_topic_status(req.topic_id, "angle_generated")
    return {"topic_id": req.topic_id, "keyword": keyword, "angles": saved}


@router.get("/by-topic/{topic_id}")
def by_topic(topic_id: int):
    return {"topic_id": topic_id, "angles": database.get_angles_by_topic(topic_id)}


def _update_topic_status(topic_id, status):
    ph = database._ph()
    with database.get_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"UPDATE ranked_topics SET status = {ph} WHERE id = {ph}", [status, topic_id])
        cur.close()
