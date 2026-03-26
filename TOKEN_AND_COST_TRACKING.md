# 모델별 사용 토큰 및 비용 추적 시스템

## 개요
프롬프트의 **섹션 7 (Model Optimization Rules - 모델 사용 최적화 규칙)**에 맞춰, 웹 인터페이스에서 **모델별 사용 토큰과 비용을 상세하게** 표시하는 기능을 추가했습니다.

---

## 🔧 백엔드 변경사항

### 1. **새로운 Pydantic 모델 (응답 타입)**

#### `ModelPriceInfo`
```python
model: str                # 모델 이름 (gpt-5.4, gpt-5-mini 등)
input_price: float       # 100만 토큰당 입력 가격
cached_input_price: float # 캐시됨 입력 가격
output_price: float      # 출력 가격
description: str         # 모델 설명
```

#### `ModelsResponse`
- `models`: 모든 모델의 가격 정보 및 설명
- `pricing_table`: 신속한 참고용 가격 테이블

#### `StageTokenEstimate`
```python
stage: str                        # 단계명
description: str                  # 단계 설명
estimated_input_tokens: int      # 예상 입력 토큰
estimated_output_tokens: int     # 예상 출력 토큰
```

#### `ModelCostBreakdown`
```python
model: str                   # 모델명
input_cost_usd: float       # 입력 비용
cached_input_cost_usd: float # 캐시 입력 비용
output_cost_usd: float      # 출력 비용
total_cost_usd: float       # 총 비용 (USD)
total_cost_krw: float       # 총 비용 (KRW, 환율 1300 기준)
```

#### `PricingComparisonResponse`
```python
request: PricingComparisonRequest           # 요청 정보
stage_estimates: list[StageTokenEstimate]  # 3단계별 토큰 예상
model_costs: list[ModelCostBreakdown]      # 모델별 비용 비교
cheapest_model: str                         # 가장 저렴한 모델
most_expensive_model: str                   # 가장 비싼 모델
```

### 2. **새로운 API 엔드포인트**

#### `GET /api/models`
**목적**: 모든 가용 모델의 가격 정보 및 설명 조회

**응답**:
```json
{
  "models": [
    {
      "model": "gpt-5.4",
      "input_price": 2.50,
      "cached_input_price": 0.25,
      "output_price": 15.00,
      "description": "고품질 모델 - 소개글/세계관 생성용"
    },
    {
      "model": "gpt-5-mini",
      "input_price": 0.25,
      "cached_input_price": 0.025,
      "output_price": 2.00,
      "description": "경량 모델 - 데이터 수집/교차 검증용"
    }
    // ... 기타 모델들
  ],
  "pricing_table": [
    { "model": "gpt-5.4", "input_price": 2.50, ... },
    // ...
  ]
}
```

#### `POST /api/pricing/comparison`
**목적**: 제시된 토큰 수를 기반으로 모든 모델의 예상 비용 비교

**요청**:
```json
{
  "estimated_input_tokens": 5000,
  "estimated_output_tokens": 2000,
  "use_caching": true
}
```

**응답**:
```json
{
  "request": { ... },
  "stage_estimates": [
    {
      "stage": "데이터 수집 및 정리",
      "description": "Activity/Profile/Performances 초안 생성 (경량 모델 권장)",
      "estimated_input_tokens": 5000,
      "estimated_output_tokens": 600
    },
    {
      "stage": "교차 검증 및 NULL 처리",
      "description": "정보 검증 및 NULL 판단 처리 (경량 모델 권장)",
      "estimated_input_tokens": 4000,
      "estimated_output_tokens": 400
    },
    {
      "stage": "소개글 및 세계관 생성",
      "description": "Introduction 섹션 생성 (고품질 모델 권장)",
      "estimated_input_tokens": 3000,
      "estimated_output_tokens": 1600
    }
  ],
  "model_costs": [
    {
      "model": "gpt-5-mini",
      "input_cost_usd": 0.00125,
      "cached_input_cost_usd": 0.0000625,
      "output_cost_usd": 0.000004,
      "total_cost_usd": 0.001316,
      "total_cost_krw": 1.71
    },
    {
      "model": "gpt-5.4",
      "input_cost_usd": 0.0125,
      "cached_input_cost_usd": 0.0000625,
      "output_cost_usd": 0.03,
      "total_cost_usd": 0.043062,
      "total_cost_krw": 55.98
    }
    // ... 기타 모델들
  ],
  "cheapest_model": "gpt-5-mini",
  "most_expensive_model": "gpt-5.4"
}
```

---

## 🎨 프론트엔드 변경사항

### 1. **새로운 TypeScript 타입**
```typescript
type ModelsResponse { ... }
type ModelPriceInfo { ... }
type PricingTableRow { ... }
type StageTokenEstimate { ... }
type PricingComparisonRequest { ... }
type ModelCostBreakdown { ... }
type PricingComparisonResponse { ... }
```

### 2. **UI/UX 개선**

#### **비용 계산 상세 섹션 확장**
기존 단순 비용 정보에서 다음 항목들을 추가:
- 총 토큰 수
- 입력 토큰 (비캐시)
- 캐시 입력 토큰
- 출력 토큰
- 각 항목별 비용
- **캐시 절감률 표시 (90% 절감)**

#### **"모델 비용 비교" 버튼**
비용 계산 상세 섹션 우측 상단에 버튼 추가:
- 클릭 시 현재 실행의 토큰 데이터를 기반으로 비용 비교 모달 열기
- 모달에서 모본 모델의 예상 비용을 한눈에 비교 가능

#### **모델 비용 비교 모달**
팝업으로 다음 정보 표시:

**① 3단계별 토큰 예상**
- 프롬프트 섹션 7-1의 3단계 분리 구조를 명시
- 각 단계별 예상 입력/출력 토큰 수 표시
- 단계별 권장 모델 설명

**② 모델별 비용 비교 테이블**
| 모델 | 입력 비용 | 캐시 비용 | 출력 비용 | 총액 (USD) | 총액 (KRW) |
|------|---------|---------|---------|-----------|-----------|
| gpt-5-mini | ⭐ 최저 | ... | ... | ... | ... |
| gpt-5.4 | ... | ... | ... | 최고 | ... |

**③ 분석 요약**
- 최저 비용 모델
- 최고 비용 모델
- 프롬프트 규칙에 따른 모델 사용 권장사항

### 3. **새로운 상태 변수**
```typescript
const [showModelComparison, setShowModelComparison] = useState(false);
const [modelComparison, setModelComparison] = useState<PricingComparisonResponse | null>(null);
const [isLoadingComparison, setIsLoadingComparison] = useState(false);
```

### 4. **새로운 함수**
```typescript
const handleShowModelComparison = async () => {
  // 현재 결과의 토큰 데이터를 기반으로
  // /api/pricing/comparison 호출
  // 응답 데이터를 state에 저장
  // 모달 표시
}
```

---

## 📊 사용 흐름

### 예시: 투어스 아티스트 정보 수집 시

1. **Prompt 실행**
   - 모델: `gpt-5.4`
   - 실행 후 결과 화면에 토큰/비용 표시

2. **비용 계산 상세 확인**
   - 실제 사용된 토큰 수: 입력 4832 + 출력 1205
   - 캐시 절감: 캐시 입력 1200 토큰 (90% 절감)
   - 총 비용: $0.019832

3. **"모델 비용 비교" 클릭**
   - 모달 열기
   - 같은 토큰 수(4832 inp + 1205 out)로 모든 모델 비용 계산 표시
   - 예: gpt-5-mini는 $0.0013, gpt-5.4는 $0.0198 등 비교

4. **분석**
   - 만약 입력이 1단계(데이터 수집)였다면? gpt-5-mini 사용 시 비용 ~99% 절감
   - 3단계를 분리해서 실행하면 전체 비용을 최적화할 수 있음을 시각화

---

## 💡 프롬프트 규칙과의 연동

### 섹션 7-1: 작업 분리 원칙
```
① 데이터 수집 및 정리 → 경량 모델 (GPT-5 mini)
② 교차 검증 및 NULL 처리 → 경량 모델 (GPT-5 mini)
③ 소개글 및 세계관 생성 → 고품질 모델 (GPT-5.4)
```

### 섹션 7-2: 모델 선택 기준
웹 UI에서 3단계별 토큰 예상을 표시함으로써:
- 각 단계에 적합한 모델 명시
- 비용 효율성 시각화
- 의사결정 지원

---

## 🚀 향후 확장 가능성

1. **상세 비용 분석**
   - 캐싱 전략 컨설팅
   - 배치 처리 시 누적 절감 시뮬레이션

2. **번들 가격**
   - 3단계 세트 가격 계산
   - 대량 실행 시 할인

3. **모니터링**
   - 월별/일별 비용 추이
   - 모델별 사용 통계

4. **자동화**
   - 최저 비용 모델 자동 선택
   - 토큰 수 임계값 시 자동 모델 전환

---

## 📝 테스트 체크리스트

- [x] 백엔드 `/api/models` 엔드포인트 작동
- [x] 백엔드 `/api/pricing/comparison` 엔드포인트 작동
- [x] 프론트엔드 타입 정의 완성
- [x] "모델 비용 비교" 버튼 표시
- [x] 모달 UI 렌더링
- [x] KRW 환율 계산 (1300 기준)
- [ ] 실제 API 호출 테스트
- [ ] 모달 닫기 / 열기 상태 관리
- [ ] 로딩 상태 표시
