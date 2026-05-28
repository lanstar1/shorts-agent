"""
DB 연결 (SQLite 로컬 / PostgreSQL Render 듀얼) + 스키마 초기화
order-agent의 듀얼 DB 패턴 준수.
"""
import sqlite3
import json
import sys
import os
from contextlib import contextmanager

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

IS_PG = bool(config.DATABASE_URL)

if IS_PG:
    import psycopg2
    import psycopg2.extras


@contextmanager
def get_conn():
    if IS_PG:
        conn = psycopg2.connect(config.DATABASE_URL)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()
    else:
        conn = sqlite3.connect(config.SQLITE_PATH)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


def _ph():
    """placeholder: PG는 %s, SQLite는 ?"""
    return "%s" if IS_PG else "?"


# JSONB(PG) vs TEXT(SQLite) 처리 헬퍼
def dump_json(obj):
    return json.dumps(obj, ensure_ascii=False)


def load_json(val):
    if val is None:
        return None
    if isinstance(val, (dict, list)):
        return val
    return json.loads(val)


def init_db():
    """테이블 생성 (IF NOT EXISTS). order-agent의 init_db 패턴."""
    json_type = "JSONB" if IS_PG else "TEXT"
    serial = "SERIAL PRIMARY KEY" if IS_PG else "INTEGER PRIMARY KEY AUTOINCREMENT"
    ts_default = "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"

    with get_conn() as conn:
        cur = conn.cursor()

        # 1. 매일 수집되는 raw 후보 신호
        cur.execute(f"""
        CREATE TABLE IF NOT EXISTS topic_candidates (
            id {serial},
            collected_date DATE NOT NULL,
            source TEXT NOT NULL,          -- 'naver_datalab','reddit','hackernews','youtube','coupang'
            axis TEXT,                     -- 'apple','samsung','lanstar_core','appliance'
            keyword TEXT,                  -- 매칭된 키워드
            title TEXT,                    -- 원본 제목/주제
            signal_type TEXT,              -- 'search_up','hot_post','rank_up','discount' 등
            signal_value REAL,             -- 신호 강도 (정규화 전)
            url TEXT,
            raw_data {json_type},          -- 출처별 원본
            created_at {ts_default}
        )
        """)

        # 2. 점수화 후 랭킹된 주제 (자동) + 수동 키워드 입력 (수동) 공통
        cur.execute(f"""
        CREATE TABLE IF NOT EXISTS ranked_topics (
            id {serial},
            ranked_date DATE NOT NULL,
            entry_mode TEXT DEFAULT 'auto',  -- 'auto'(자동소싱) / 'manual'(키워드입력)
            axis TEXT,
            keyword TEXT,
            title TEXT,
            total_score REAL,
            score_breakdown {json_type},
            research_data {json_type},       -- 수동모드: on-demand 조사 결과
            coupang_monetizable INTEGER DEFAULT 0,
            candidate_ids {json_type},
            status TEXT DEFAULT 'pending',  -- pending/angle_generated/used/rejected
            created_at {ts_default}
        )
        """)

        # 3. 생성된 스토리 앵글 (2주차)
        cur.execute(f"""
        CREATE TABLE IF NOT EXISTS story_angles (
            id {serial},
            ranked_topic_id INTEGER,
            generated_date DATE NOT NULL,
            angle_type TEXT,               -- expectation_gap/hidden_truth/market_shock
            title TEXT,                    -- "~ㄷㄷ" 형식 제목
            hook TEXT,                     -- 0~2초 훅
            data_points {json_type},       -- 핵심 데이터 3개
            closing_question TEXT,         -- 질문형 클로징
            curation_score REAL,           -- Claude 2차 큐레이션 점수
            selected_for_today INTEGER DEFAULT 0,
            created_at {ts_default}
        )
        """)

        # 인덱스
        cur.execute("CREATE INDEX IF NOT EXISTS idx_cand_date ON topic_candidates(collected_date)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_ranked_date ON ranked_topics(ranked_date)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_angle_date ON story_angles(generated_date)")

        conn.commit()
        cur.close()


def insert_candidate(row: dict):
    """topic_candidates에 1건 삽입"""
    ph = _ph()
    cols = ["collected_date", "source", "axis", "keyword", "title",
            "signal_type", "signal_value", "url", "raw_data"]
    vals = [
        row.get("collected_date"),
        row.get("source"),
        row.get("axis"),
        row.get("keyword"),
        row.get("title"),
        row.get("signal_type"),
        row.get("signal_value"),
        row.get("url"),
        dump_json(row.get("raw_data")) if row.get("raw_data") is not None else None,
    ]
    placeholders = ", ".join([ph] * len(cols))
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"INSERT INTO topic_candidates ({', '.join(cols)}) VALUES ({placeholders})",
            vals,
        )
        cur.close()


def count_candidates_by_date(date_str):
    ph = _ph()
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT source, COUNT(*) FROM topic_candidates WHERE collected_date = {ph} GROUP BY source",
            [date_str],
        )
        rows = cur.fetchall()
        cur.close()
        return {r[0]: r[1] for r in rows}


def insert_ranked_topic(row: dict):
    """ranked_topics에 1건 삽입하고 id 반환 (자동/수동 공통)"""
    ph = _ph()
    cols = ["ranked_date", "entry_mode", "axis", "keyword", "title",
            "total_score", "score_breakdown", "research_data",
            "coupang_monetizable", "candidate_ids", "status"]
    vals = [
        row.get("ranked_date"),
        row.get("entry_mode", "auto"),
        row.get("axis"),
        row.get("keyword"),
        row.get("title"),
        row.get("total_score", 0),
        dump_json(row.get("score_breakdown")) if row.get("score_breakdown") is not None else None,
        dump_json(row.get("research_data")) if row.get("research_data") is not None else None,
        1 if row.get("coupang_monetizable") else 0,
        dump_json(row.get("candidate_ids")) if row.get("candidate_ids") is not None else None,
        row.get("status", "pending"),
    ]
    placeholders = ", ".join([ph] * len(cols))
    returning = " RETURNING id" if IS_PG else ""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"INSERT INTO ranked_topics ({', '.join(cols)}) VALUES ({placeholders}){returning}",
            vals,
        )
        if IS_PG:
            new_id = cur.fetchone()[0]
        else:
            new_id = cur.lastrowid
        cur.close()
        return new_id


def get_ranked_topic(topic_id):
    ph = _ph()
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM ranked_topics WHERE id = {ph}", [topic_id])
        row = cur.fetchone()
        cur.close()
        if not row:
            return None
        cols = [d[0] for d in cur.description] if cur.description else []
        return dict(zip(cols, row)) if cols else dict(row)


def insert_story_angle(row: dict):
    """story_angles에 1건 삽입하고 id 반환"""
    ph = _ph()
    cols = ["ranked_topic_id", "generated_date", "angle_type", "title", "hook",
            "data_points", "closing_question", "curation_score", "selected_for_today"]
    vals = [
        row.get("ranked_topic_id"),
        row.get("generated_date"),
        row.get("angle_type"),
        row.get("title"),
        row.get("hook"),
        dump_json(row.get("data_points")) if row.get("data_points") is not None else None,
        row.get("closing_question"),
        row.get("curation_score", 0),
        1 if row.get("selected_for_today") else 0,
    ]
    placeholders = ", ".join([ph] * len(cols))
    returning = " RETURNING id" if IS_PG else ""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"INSERT INTO story_angles ({', '.join(cols)}) VALUES ({placeholders}){returning}",
            vals,
        )
        new_id = cur.fetchone()[0] if IS_PG else cur.lastrowid
        cur.close()
        return new_id


def get_angles_by_topic(topic_id):
    ph = _ph()
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"""SELECT id, angle_type, title, hook, data_points, closing_question, curation_score
                FROM story_angles WHERE ranked_topic_id = {ph}
                ORDER BY id""",
            [topic_id],
        )
        rows = cur.fetchall()
        cur.close()
        out = []
        for r in rows:
            out.append({
                "id": r[0], "angle_type": r[1], "title": r[2], "hook": r[3],
                "data_points": load_json(r[4]), "closing_question": r[5],
                "curation_score": r[6],
            })
        return out


if __name__ == "__main__":
    init_db()
    print(f"DB 초기화 완료 (mode={'PostgreSQL' if IS_PG else 'SQLite'})")
