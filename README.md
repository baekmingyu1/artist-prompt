# Artist Prompt Runner

`[System Prompt] 아티스트 정보 수집 및 검증 시스템.txt`를 로컬에서 바로 불러와 실행하고, 샘플 JSON과 결과물을 함께 검증할 수 있는 테스트 웹입니다.  
구성은 `FastAPI` 백엔드와 `React + TypeScript + Vite` 프론트엔드이며, 아티스트 정보 수집용 프롬프트를 빠르게 반복 검증하는 용도에 맞춰져 있습니다.

## 문제

- 시스템 프롬프트를 수정할 때마다 별도 툴에서 프롬프트, 샘플 입력, 실행 결과를 분리해서 확인해야 했습니다.
- 아티스트별 샘플 JSON과 실제 응답 결과를 한 화면에서 비교하기 어려웠습니다.
- 토큰 사용량, 예상 비용, 웹 검색 사용 여부 같은 실행 메타데이터를 누적해서 보기 어려웠습니다.

## 목표

- 루트 폴더의 시스템 프롬프트와 샘플 JSON을 자동으로 불러온다.
- 아티스트명 치환, 사용자 프롬프트 수정, 웹 검색 옵션 변경을 UI에서 즉시 테스트한다.
- 실행 결과를 `Raw Output`, `Parsed JSON`, `HTML 미리보기`, `실행 이력` 기준으로 한 번에 검증한다.
- 반복 테스트 과정에서 발생하는 로컬 산출물은 Git 관리 대상과 분리한다.

## 요구사항

| ID | 구분 | 요구사항 설명 | 우선순위 | 비고 |
|----|------|----------------|----------|------|
| RQ-01 | 프롬프트 로딩 | 루트 경로의 `[System Prompt]*.txt` 파일을 자동 탐색해 기본 시스템 프롬프트로 로드해야 한다. | 높음 | 첫 번째 매칭 파일 사용 |
| RQ-02 | 샘플 로딩 | 루트 경로의 `.json` 파일을 샘플 목록으로 제공해야 한다. | 높음 | `-preview.json` 제외 |
| RQ-03 | 실행 옵션 | 아티스트명, 모델, reasoning effort, 웹 검색 사용 여부를 UI에서 조정할 수 있어야 한다. | 높음 | `%아티스트명%` 치환 포함 |
| RQ-04 | 결과 검증 | 실행 결과는 원문 응답과 JSON 파싱 결과를 동시에 보여줘야 한다. | 높음 | JSON 파싱 실패 시 원문 유지 |
| RQ-05 | 실행 이력 | 최근 실행 이력을 로컬에 저장하고, 다시 조회할 수 있어야 한다. | 중간 | 최근 100건 유지 |
| RQ-06 | 비용 가시화 | 토큰 사용량과 모델 기준 예상 비용을 함께 표시해야 한다. | 중간 | USD 기준 |
| RQ-07 | 시각 검증 | 파싱된 JSON 결과를 HTML 미리보기로 열어 빠르게 검토할 수 있어야 한다. | 중간 | 프론트에서 Blob HTML 생성 |

## 폴더 구조

```text
.
├─ backend/
│  ├─ app/main.py
│  ├─ requirements.txt
│  └─ .env.example
├─ frontend/
│  ├─ src/App.tsx
│  ├─ package.json
│  └─ .env.example
├─ [System Prompt] 아티스트 정보 수집 및 검증 시스템.txt
├─ *.json
└─ README.md
```

## 주요 기능

- 시스템 프롬프트 `.txt` 자동 로드
- 샘플 JSON 자동 탐색 및 선택 로드
- `%아티스트명%` 치환 기반 실행
- OpenAI `Responses API` 3단계 파이프라인 호출
- `Raw Output` / `Parsed JSON` 동시 확인
- 결과 JSON 기반 HTML 미리보기 생성
- 실행 이력 로컬 저장
- 단계별 모델, 토큰, 예상 비용 표시

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

### 2. 프론트엔드 실행

```bash
cd frontend
npm install
copy .env.example .env
npm run dev
```

### 3. 접속 주소

- 프론트엔드: `http://localhost:5173`
- 백엔드 API 문서: `http://localhost:8000/docs`

## 환경 변수

### backend/.env

| 키 | 설명 | 예시 |
|----|------|------|
| `OPENAI_API_KEY` | OpenAI API Key | `sk-...` |
| `OPENAI_MODEL` | 기본 실행 모델 또는 introduction 기본 모델 | `gpt-5.4` |
| `OPENAI_BASE_URL` | OpenAI 기본 URL 또는 커스텀 API URL | `https://api.openai.com/v1` |
| `ALLOWED_ORIGIN` | 프론트엔드 허용 출처 | `http://localhost:5173` |

### frontend/.env

| 키 | 설명 | 예시 |
|----|------|------|
| `VITE_API_BASE_URL` | 백엔드 API 기본 주소 | `http://localhost:8000` |

## 사용 흐름

1. 루트 폴더에 시스템 프롬프트 `.txt`와 샘플 `.json`을 둡니다.
2. 프론트에서 샘플 JSON을 선택해 기준 결과를 확인합니다.
3. 아티스트명, 기본 모델, 단계별 모델, reasoning, 웹 검색 사용 여부를 설정합니다.
4. 사용자 프롬프트를 입력하고 실행합니다.
5. 결과를 `단계별 실행`, `비용 계산 상세`, `Raw Output`, `Parsed JSON`, `HTML 보기`, `실행 이력`으로 검증합니다.

## API 요약

| Method | Path | 설명 |
|----|------|------|
| `GET` | `/health` | 헬스 체크 |
| `GET` | `/api/bootstrap` | 기본 프롬프트, 샘플 목록, 기본 모델 조회 |
| `GET` | `/api/history` | 최근 실행 이력 조회 |
| `GET` | `/api/samples/{file_name}` | 샘플 JSON 조회 |
| `POST` | `/api/run` | 프롬프트 실행 및 결과 저장 |

## 예외/에러

- `OPENAI_API_KEY`가 없으면 실행 API는 `500` 오류를 반환합니다.
- 샘플 JSON이 잘못된 형식이면 샘플 조회 API에서 파싱 오류를 반환합니다.
- 모델별 가격표에 없는 모델명은 비용 계산이 `null`로 표시됩니다.
- 응답 텍스트가 JSON 형식이 아니면 `Parsed JSON`은 비어 있고 원문만 유지됩니다.
- 웹 검색 결과의 인용 링크는 JSON 값에 남지 않도록 후처리됩니다.
- 각 단계 응답이 JSON으로 파싱되지 않으면 실행이 실패합니다.

## 브랜치 전략

### 기본 원칙

- `main`은 항상 실행 가능한 상태만 유지합니다.
- 직접 작업은 `feature/*`, `fix/*`, `docs/*`, `chore/*` 브랜치에서 진행합니다.
- 하나의 브랜치는 하나의 목적만 갖도록 나눕니다.

### 브랜치 네이밍

| 유형 | 형식 | 예시 |
|------|------|------|
| 기능 개발 | `feature/<topic>` | `feature/history-filter` |
| 버그 수정 | `fix/<topic>` | `fix/json-parse-error` |
| 문서 작업 | `docs/<topic>` | `docs/readme-refresh` |
| 환경/설정 | `chore/<topic>` | `chore/gitignore-update` |

### 권장 작업 절차

1. `main` 최신화
2. 작업 목적에 맞는 브랜치 생성
3. 변경 후 로컬 실행 확인
4. 커밋 메시지 정리
5. PR 또는 병합 진행

### 권장 커밋 예시

- `feat: 실행 이력 필터 추가`
- `fix: JSON 파싱 실패 시 오류 처리 보강`
- `docs: README 실행 가이드 정리`
- `chore: gitignore 정리`

## 구현 참고

- 백엔드는 `FastAPI`, `openai`, `python-dotenv`를 사용합니다.
- 프론트엔드는 `React 19`, `TypeScript`, `Vite` 기반입니다.
- 실행 이력은 `backend/data/run_history.json`에 최근 100건까지 저장합니다.
- 비용 계산은 코드에 정의된 모델별 `per 1M tokens` 기준표를 사용합니다.
- 웹 검색 사용 시 최종 JSON 출력에 출처 링크가 남지 않도록 후처리합니다.
- 실행은 `수집/정리 -> 검증/정리 -> introduction 생성` 3단계로 분리되며, 단계별 모델을 다르게 지정할 수 있습니다.

## 비고

- 현재 결과 검증은 "응답 텍스트를 JSON으로 파싱 가능한가"에 초점이 맞춰져 있습니다.
- JSON 스키마 강제 검증이나 필드 단위 diff 비교는 아직 포함되어 있지 않습니다.
- 테스트 편의상 로컬 미리보기 HTML은 파일 저장 없이 브라우저 Blob으로 엽니다.
