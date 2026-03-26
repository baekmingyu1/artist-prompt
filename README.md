# Codex Prompt Runner

`[System Prompt] 아티스트 정보 수집 및 검증 시스템.txt`를 바로 불러와서 테스트할 수 있는 웹 시스템입니다.  
구성은 `FastAPI(Python)` 백엔드와 `React + TypeScript(Vite)` 프론트엔드입니다.

## 폴더 구조

```text
backend/
  app/main.py
frontend/
  src/App.tsx
```

## 기능

- 루트 폴더의 시스템 프롬프트 `.txt` 자동 로드
- 루트 폴더의 샘플 `.json` 자동 탐색 및 로드
- 아티스트명 `%아티스트명%` 치환
- OpenAI Responses API 기반 프롬프트 실행
- Raw 응답 / JSON 파싱 결과 동시 확인
- 실행 이력 로컬 저장
- 실행 건별 토큰 / 비용 표시

## 실행 방법

### 1. 백엔드 실행

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --port 8000
```

`.env` 설정 항목:

| 키 | 설명 | 예시 |
|----|------|------|
| `OPENAI_API_KEY` | OpenAI API Key | `sk-...` |
| `OPENAI_MODEL` | 기본 실행 모델 | `gpt-5.4` |
| `OPENAI_BASE_URL` | OpenAI 기본 URL 또는 커스텀 API URL | `https://api.openai.com/v1` |
| `ALLOWED_ORIGIN` | 프론트엔드 허용 출처 | `http://localhost:5173` |

### 2. 프론트엔드 실행

```bash
cd frontend
npm install
copy .env.example .env
npm run dev
```

기본 접속 주소:

- 프론트엔드: `http://localhost:5173`
- 백엔드 Swagger: `http://localhost:8000/docs`

## API 요약

| Method | Path | 설명 |
|----|------|------|
| `GET` | `/health` | 헬스 체크 |
| `GET` | `/api/bootstrap` | 기본 프롬프트/샘플 목록 조회 |
| `GET` | `/api/history` | 최근 실행 이력 조회 |
| `GET` | `/api/samples/{file_name}` | 샘플 JSON 조회 |
| `POST` | `/api/run` | Codex/OpenAI 실행 |

## 구현 참고

- OpenAI 공식 문서 기준으로 `Responses API` 호출 구조를 사용했습니다.
- 현재 기본 모델은 `gpt-5.4`입니다. OpenAI 모델 문서의 최신 모델 안내에서는 복잡한 추론/코딩 작업 시작점으로 `gpt-5.4`를 권장하고 있습니다.
- 비용 계산 기준도 GPT-5 계열 모델 단가에 맞춰 반영했습니다. 필요하면 프론트에서 모델명을 바꿔 비교 테스트하면 됩니다.
- 실행 이력은 `backend/data/run_history.json`에 최근 100건까지 저장합니다.
- 현재 JSON 강제 스키마 검증은 넣지 않았고, 우선 응답 텍스트를 로컬에서 JSON 파싱하는 방식으로 구성했습니다.
