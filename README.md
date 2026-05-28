# shorts-agent

맥가이버 스타일 IT/전자제품 유튜브 쇼츠 **주제 발굴 + 스토리텔링 앵글** 자동화 시스템.

> AI가 매일 아침 주제와 앵글을 추천하고, 사람은 선택만 한다.
> 영상 촬영·음성 녹음은 사용자가 직접 준비하며, 이 시스템은 **주제 발굴 → 앵글 → 스크립트 → 자막/효과음** 자산만 생성한다.

## 단계별 로드맵

| 단계 | 내용 | 상태 |
|---|---|---|
| **1단계** | 주제 발굴 (4개 소스 수집 + 점수화) | 🚧 진행중 (수집기 완료) |
| **2단계** | 스토리텔링 앵글 생성 (Claude) | ⏳ 예정 |
| 3단계 | 스크립트 생성 (대본/컷리스트/B-roll) | ⏳ |
| 4단계 | 자막(SRT/FCPXML/MOV) + 효과음(MP3) 렌더 | ⏳ |

## 맥가이버 분석 핵심 (설계 근거)

30편 정밀 분석 결과:
- **브랜드 서사로 주제 선정**: 애플 22편 / 삼성 18편 (거의 100%)
- 스마트폰 20편 압도, 하루 1편, 평균 25.7초
- 질문형 클로징 83%
- 후킹 유형: 기대갭 > 가격 = 의문형 > 반전/배신 > 충격

→ 4축 키워드 전략: 애플(35%) / 삼성(30%) / 본업(25%) / 가전(10%)

## 데이터 소스 (1단계)

| 소스 | 인증 | 역할 |
|---|---|---|
| 네이버 데이터랩 | API 키 | 한국 검색 트렌드 증가율 |
| 레딧 공개 JSON | 불필요 | 글로벌 디바이스 이슈/루머 |
| 해커뉴스 | 불필요 | 글로벌 테크 이슈 |
| 쿠팡 파트너스 | HMAC | 할인/베스트 + 수익화 링크 |

## 기술 스택

FastAPI + 바닐라 JS SPA + PostgreSQL(Render)/SQLite(로컬) + APScheduler + Claude
(order-agent와 동일 패턴)

## 로컬 실행

```bash
cd backend
pip install -r requirements.txt
cp ../.env.example ../.env   # 키 입력
python -m uvicorn main:app --reload --port 8000
# → http://localhost:8000
```

## 배포 (Render)

`render.yaml` 포함. GitHub 연동 시 자동 배포. 환경변수는 Render 대시보드에서 설정.

## 주요 엔드포인트

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | /api/health | 헬스체크 |
| GET | /api/topics/candidates | 후보 조회 |
| GET | /api/topics/summary | 최근 N일 수집 현황 |
| POST | /api/topics/collect-now | 수동 즉시 수집 |
| GET | /api/topics/scheduler-status | 스케줄러 상태 |

## 키워드 풀 수정

`backend/data/keyword_pool.py` 한 파일만 수정하면 즉시 반영.
