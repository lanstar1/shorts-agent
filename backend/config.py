"""환경변수 로딩 (order-agent 패턴 준수)"""
import os
from dotenv import load_dotenv

load_dotenv()


def _get(key, default=None):
    return os.environ.get(key, default)


# ===== Anthropic (앵글 생성용) =====
ANTHROPIC_API_KEY = _get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = _get("ANTHROPIC_MODEL", "claude-sonnet-4-6")

# ===== 네이버 데이터랩 / 검색 (order-agent와 동일 키 재사용) =====
NAVER_SEARCH_ID = _get("NAVER_SEARCH_ID", "")
NAVER_SEARCH_SECRET = _get("NAVER_SEARCH_SECRET", "")

# ===== 쿠팡 파트너스 =====
COUPANG_ACCESS_KEY = _get("COUPANG_ACCESS_KEY", "")
COUPANG_SECRET_KEY = _get("COUPANG_SECRET_KEY", "")

# ===== YouTube Data API v3 (선택, 경쟁사 트렌드 추적) =====
YOUTUBE_API_KEY = _get("YOUTUBE_API_KEY", "")

# ===== OpenAI Whisper (음성 STT 자막 정렬) =====
OPENAI_API_KEY = _get("OPENAI_API_KEY", "")

# ===== DB =====
DATABASE_URL = _get("DATABASE_URL", "")  # Render: postgresql://...  / 로컬: 빈값이면 SQLite
SQLITE_PATH = _get("SQLITE_PATH", "shorts_agent.db")

# ===== 스케줄러 =====
COLLECT_HOUR_KST = int(_get("COLLECT_HOUR_KST", "8"))  # 매일 아침 8시 수집
DAILY_ANGLE_COUNT = int(_get("DAILY_ANGLE_COUNT", "3"))  # 매일 엄선 앵글 개수

# ===== 수집 설정 =====
REDDIT_USER_AGENT = _get("REDDIT_USER_AGENT", "shorts-agent/0.1 (by lanstar1)")
HTTP_TIMEOUT = int(_get("HTTP_TIMEOUT", "15"))
