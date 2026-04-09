import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from openai import OpenAI


load_dotenv()

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "backend" / "data"
HISTORY_FILE = DATA_DIR / "run_history.json"
PROMPT_GLOB = "[[]System Prompt[]]*.txt"
SAMPLE_PATTERN = "*.json"
MODEL_PRICING_PER_1M_TOKENS: dict[str, dict[str, float]] = {
    "gpt-5.4": {"input": 2.50, "cached_input": 0.25, "output": 15.00},
    "gpt-5": {"input": 1.25, "cached_input": 0.125, "output": 10.00},
    "gpt-5-mini": {"input": 0.25, "cached_input": 0.025, "output": 2.00},
    "gpt-5-nano": {"input": 0.05, "cached_input": 0.005, "output": 0.40},
    "gpt-5-codex": {"input": 1.25, "cached_input": 0.125, "output": 10.00},
    "gpt-5.1-codex": {"input": 1.25, "cached_input": 0.125, "output": 10.00},
    "gpt-5.1-codex-mini": {"input": 0.25, "cached_input": 0.025, "output": 2.00},
}


def find_prompt_file() -> Path | None:
    files = sorted(ROOT_DIR.glob(PROMPT_GLOB))
    return files[0] if files else None


def list_sample_files() -> list[Path]:
    return sorted(
        path
        for path in ROOT_DIR.glob(SAMPLE_PATTERN)
        if path.is_file() and not path.name.endswith("-preview.json")
    )


def read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class RunRequest(BaseModel):
    system_prompt: str = Field(..., min_length=1)
    user_prompt: str = Field(..., min_length=1)
    artist_name: str = ""
    model: str = Field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-5.4"))
    stage_models: dict[str, str] | None = None
    reasoning_effort: str = "medium"
    use_web_search: bool = True


class SampleResponse(BaseModel):
    name: str
    content: Any


class BootstrapResponse(BaseModel):
    prompt_file_name: str | None
    system_prompt: str
    sample_files: list[str]
    default_model: str


class RunResponse(BaseModel):
    run_id: str
    created_at: str
    model: str
    stage_models: dict[str, str]
    artist_name: str
    reasoning_effort: str
    use_web_search: bool
    output_text: str
    parsed_json: Any | None
    usage: dict[str, Any]
    pricing: dict[str, Any]
    stage_results: list[dict[str, Any]]
    web_sources: list[dict[str, Any]]
    duration_ms: int


class HistoryItem(BaseModel):
    run_id: str
    created_at: str
    model: str
    stage_models: dict[str, str] = Field(default_factory=dict)
    artist_name: str
    reasoning_effort: str
    use_web_search: bool = False
    duration_ms: int
    usage: dict[str, Any]
    pricing: dict[str, Any]
    stage_results: list[dict[str, Any]] = Field(default_factory=list)
    web_source_count: int = 0
    output_preview: str
    parsed_json: Any | None = None


class ModelPriceInfo(BaseModel):
    model: str
    input_price: float
    cached_input_price: float
    output_price: float
    description: str


class PricingTableRow(BaseModel):
    model: str
    input_price: float
    cached_input_price: float
    output_price: float


class ModelsResponse(BaseModel):
    models: list[ModelPriceInfo]
    pricing_table: list[PricingTableRow]


class StageTokenEstimate(BaseModel):
    stage: str
    description: str
    estimated_input_tokens: int
    estimated_output_tokens: int


class PricingComparisonRequest(BaseModel):
    estimated_input_tokens: int = 5000
    estimated_output_tokens: int = 2000
    use_caching: bool = True


class ModelCostBreakdown(BaseModel):
    model: str
    input_cost_usd: float
    cached_input_cost_usd: float
    output_cost_usd: float
    total_cost_usd: float


class PricingComparisonResponse(BaseModel):
    request: PricingComparisonRequest
    stage_estimates: list[StageTokenEstimate]
    model_costs: list[ModelCostBreakdown]
    cheapest_model: str
    most_expensive_model: str


app = FastAPI(title="Codex Prompt Runner")

allowed_origin = os.getenv("ALLOWED_ORIGIN", "http://localhost:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[allowed_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY가 설정되지 않았습니다.")

    base_url = (os.getenv("OPENAI_BASE_URL") or "").strip() or "https://api.openai.com/v1"
    return OpenAI(api_key=api_key, base_url=base_url)


def parse_json_text(text: str) -> Any | None:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        parts = cleaned.split("```")
        if len(parts) >= 3:
            cleaned = parts[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
    cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Fall back to the first complete JSON object/array when the model adds prose.
    starts = [idx for idx in (cleaned.find("{"), cleaned.find("[")) if idx != -1]
    if not starts:
        return None

    decoder = json.JSONDecoder()
    for start in sorted(starts):
        try:
            parsed, _ = decoder.raw_decode(cleaned[start:])
            return parsed
        except json.JSONDecodeError:
            continue
    return None


def strip_inline_citations(text: str) -> str:
    cleaned = text
    cleaned = re.sub(r"\s*\(\[https?://[^\]]+\]\([^)]+\)\)", "", cleaned)
    cleaned = re.sub(r"\s*\(\[[^\]]+\]\([^)]+\)\)", "", cleaned)
    cleaned = re.sub(r"\s*\[[^\]]+\]\(https?://[^)]+\)", "", cleaned)
    cleaned = re.sub(r"\s*https?://\S+", "", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def sanitize_json_strings(value: Any) -> Any:
    if isinstance(value, str):
        return strip_inline_citations(value)
    if isinstance(value, list):
        return [sanitize_json_strings(item) for item in value]
    if isinstance(value, dict):
        return {key: sanitize_json_strings(item) for key, item in value.items()}
    return value


def get_model_pricing(model_name: str) -> dict[str, float] | None:
    normalized = model_name.strip()
    if normalized in MODEL_PRICING_PER_1M_TOKENS:
        return MODEL_PRICING_PER_1M_TOKENS[normalized]

    for known_model, pricing in MODEL_PRICING_PER_1M_TOKENS.items():
        if normalized.startswith(f"{known_model}-"):
            return pricing

    return None


def build_usage_payload(response: Any) -> dict[str, Any]:
    usage = getattr(response, "usage", None)
    if not usage:
        return {
            "input_tokens": 0,
            "cached_input_tokens": 0,
            "output_tokens": 0,
            "reasoning_tokens": 0,
            "total_tokens": 0,
        }

    input_tokens_details = getattr(usage, "input_tokens_details", None)
    output_tokens_details = getattr(usage, "output_tokens_details", None)

    cached_input_tokens = 0
    if input_tokens_details:
        cached_input_tokens = getattr(input_tokens_details, "cached_tokens", 0) or 0

    reasoning_tokens = 0
    if output_tokens_details:
        reasoning_tokens = getattr(output_tokens_details, "reasoning_tokens", 0) or 0

    return {
        "input_tokens": getattr(usage, "input_tokens", 0) or 0,
        "cached_input_tokens": cached_input_tokens,
        "output_tokens": getattr(usage, "output_tokens", 0) or 0,
        "reasoning_tokens": reasoning_tokens,
        "total_tokens": getattr(usage, "total_tokens", 0) or 0,
    }


def build_pricing_payload(model_name: str, usage_payload: dict[str, Any]) -> dict[str, Any]:
    pricing = get_model_pricing(model_name)
    if not pricing:
        return {
            "currency": "USD",
            "estimated_cost_usd": None,
            "estimated_cost_krw": None,
            "input_cost_usd": None,
            "cached_input_cost_usd": None,
            "output_cost_usd": None,
            "price_reference": "가격 정보 없음",
        }

    input_tokens = usage_payload["input_tokens"]
    cached_input_tokens = usage_payload["cached_input_tokens"]
    non_cached_input_tokens = max(input_tokens - cached_input_tokens, 0)
    output_tokens = usage_payload["output_tokens"]

    input_cost_usd = (non_cached_input_tokens / 1_000_000) * pricing["input"]
    cached_input_cost_usd = (cached_input_tokens / 1_000_000) * pricing["cached_input"]
    output_cost_usd = (output_tokens / 1_000_000) * pricing["output"]
    estimated_cost_usd = input_cost_usd + cached_input_cost_usd + output_cost_usd

    return {
        "currency": "USD",
        "estimated_cost_usd": round(estimated_cost_usd, 8),
        "estimated_cost_krw": None,
        "input_cost_usd": round(input_cost_usd, 8),
        "cached_input_cost_usd": round(cached_input_cost_usd, 8),
        "output_cost_usd": round(output_cost_usd, 8),
        "price_reference": "per_1m_tokens",
        "price_table": pricing,
    }


def aggregate_usage_payload(usages: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "input_tokens": sum(item.get("input_tokens", 0) for item in usages),
        "cached_input_tokens": sum(item.get("cached_input_tokens", 0) for item in usages),
        "output_tokens": sum(item.get("output_tokens", 0) for item in usages),
        "reasoning_tokens": sum(item.get("reasoning_tokens", 0) for item in usages),
        "total_tokens": sum(item.get("total_tokens", 0) for item in usages),
    }


def aggregate_pricing_payload(pricings: list[dict[str, Any]]) -> dict[str, Any]:
    numeric_keys = [
        "estimated_cost_usd",
        "estimated_cost_krw",
        "input_cost_usd",
        "cached_input_cost_usd",
        "output_cost_usd",
    ]
    aggregated: dict[str, Any] = {
        "currency": "USD",
        "price_reference": "stage_sum",
        "price_table": None,
    }
    for key in numeric_keys:
        values = [item.get(key) for item in pricings if item.get(key) is not None]
        aggregated[key] = round(sum(values), 8) if values else None
    return aggregated


def build_default_stage_models(default_model: str) -> dict[str, str]:
    normalized = default_model.strip().lower()
    if normalized == "auto":
        return {
            "collection": "gpt-5-mini",
            "validation": "gpt-5-mini",
            "introduction": "gpt-5.4",
        }
    return {
        "collection": normalized,
        "validation": normalized,
        "introduction": normalized,
    }


def resolve_stage_models(payload: RunRequest) -> tuple[str, dict[str, str]]:
    normalized_model = payload.model.strip().lower()
    stage_models = build_default_stage_models(normalized_model)
    if payload.stage_models:
        for stage in ["collection", "validation", "introduction"]:
            candidate = (payload.stage_models.get(stage) or "").strip().lower()
            if candidate:
                stage_models[stage] = candidate
    if normalized_model == "auto":
        model_label = "auto-pipeline"
    elif len(set(stage_models.values())) == 1:
        model_label = next(iter(stage_models.values()))
    else:
        model_label = "custom-pipeline"
    return model_label, stage_models


def merge_artist_payload(base_payload: Any, introduction_payload: Any) -> Any:
    if not isinstance(base_payload, dict):
        return base_payload
    merged = dict(base_payload)
    introduction_value = introduction_payload
    if isinstance(introduction_payload, dict) and "introduction" in introduction_payload:
        introduction_value = introduction_payload.get("introduction")
    merged["introduction"] = introduction_value
    return merged


ARTIST_COLLECTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "artist_name": {"type": "string"},
        "activity_info": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "debut_date": {"type": "string"},
                "debut_song": {"type": "string"},
                "activity_era": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["debut_date", "debut_song", "activity_era"],
        },
        "profile": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "real_name": {"type": "string"},
                "birth_date": {"type": "string"},
                "mbti": {"type": "string"},
                "nationality": {"type": "string"},
            },
            "required": ["real_name", "birth_date", "mbti", "nationality"],
        },
        "performances": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "type": {"type": "string"},
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                    "title": {"type": "string"},
                },
                "required": ["type", "start_date", "end_date", "title"],
            },
        },
    },
    "required": ["artist_name", "activity_info", "profile", "performances"],
}


INTRODUCTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "summary": {"type": "string"},
        "universe": {"type": "string"},
        "interview": {"type": "string"},
    },
    "required": ["summary", "universe", "interview"],
}


def execute_stage(
    client: OpenAI,
    *,
    stage_name: str,
    model_name: str,
    reasoning_effort: str,
    instructions: str,
    stage_input: str,
    use_web_search: bool,
    json_schema: dict[str, Any] | None = None,
    schema_name: str | None = None,
) -> dict[str, Any]:
    tools = [{"type": "web_search"}] if use_web_search else []
    started = time.perf_counter()
    text_config: dict[str, Any] | None = None
    if json_schema and schema_name:
        text_config = {
            "format": {
                "type": "json_schema",
                "name": schema_name,
                "schema": json_schema,
                "strict": True,
            }
        }
    request_kwargs: dict[str, Any] = {
        "model": model_name,
        "reasoning": {"effort": reasoning_effort},
        "instructions": instructions,
        "input": stage_input,
        "tools": tools,
        "tool_choice": "auto" if tools else None,
        "include": ["web_search_call.action.sources"] if tools else None,
    }
    if text_config:
        request_kwargs["text"] = text_config
    response = client.responses.create(
        **request_kwargs,
    )
    duration_ms = int((time.perf_counter() - started) * 1000)
    output_text = getattr(response, "output_text", "") or ""
    parsed_json = parse_json_text(output_text)
    if parsed_json is not None:
        parsed_json = sanitize_json_strings(parsed_json)
    usage_payload = build_usage_payload(response)
    pricing_payload = build_pricing_payload(model_name, usage_payload)
    web_sources = extract_web_sources(response)
    return {
        "stage": stage_name,
        "model": model_name,
        "duration_ms": duration_ms,
        "output_text": output_text,
        "parsed_json": parsed_json,
        "usage": usage_payload,
        "pricing": pricing_payload,
        "web_sources": web_sources,
    }


def ensure_history_storage() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not HISTORY_FILE.exists():
        HISTORY_FILE.write_text("[]", encoding="utf-8")


def load_history() -> list[dict[str, Any]]:
    ensure_history_storage()
    try:
        records = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []

    normalized_records: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            continue

        normalized = {
            "run_id": record.get("run_id", str(uuid4())),
            "created_at": record.get("created_at", datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")),
            "model": record.get("model", ""),
            "stage_models": record.get("stage_models", {}),
            "artist_name": record.get("artist_name", ""),
            "reasoning_effort": record.get("reasoning_effort", "medium"),
            "use_web_search": record.get("use_web_search", False),
            "duration_ms": record.get("duration_ms", 0),
            "usage": record.get("usage", {}),
            "pricing": record.get("pricing", {}),
            "stage_results": record.get("stage_results", []),
            "web_source_count": record.get("web_source_count", 0),
            "output_preview": record.get("output_preview", ""),
            "parsed_json": record.get("parsed_json"),
        }
        normalized_records.append(normalized)

    return normalized_records


def save_history(records: list[dict[str, Any]]) -> None:
    ensure_history_storage()
    HISTORY_FILE.write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def append_history(record: dict[str, Any]) -> None:
    records = load_history()
    records.insert(0, record)
    save_history(records[:100])


def build_output_preview(output_text: str, limit: int = 180) -> str:
    compact = " ".join(output_text.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit].rstrip()}..."


def extract_web_sources(response: Any) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    output = getattr(response, "output", None) or []

    for item in output:
        if getattr(item, "type", None) != "web_search_call":
            continue

        action = getattr(item, "action", None)
        action_sources = getattr(action, "sources", None) if action else None
        if not action_sources:
            continue

        for source in action_sources:
            sources.append(
                {
                    "type": getattr(source, "type", None),
                    "title": getattr(source, "title", None),
                    "url": getattr(source, "url", None),
                }
            )

    unique_sources: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source in sources:
        key = source.get("url") or source.get("title") or ""
        if not key or key in seen:
            continue
        seen.add(key)
        unique_sources.append(source)

    return unique_sources


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/bootstrap", response_model=BootstrapResponse)
def get_bootstrap() -> BootstrapResponse:
    prompt_file = find_prompt_file()
    sample_files = [path.name for path in list_sample_files()]
    system_prompt = read_text_file(prompt_file) if prompt_file else ""

    return BootstrapResponse(
        prompt_file_name=prompt_file.name if prompt_file else None,
        system_prompt=system_prompt,
        sample_files=sample_files,
        default_model=os.getenv("OPENAI_MODEL", "gpt-5.4"),
    )


@app.get("/api/history", response_model=list[HistoryItem])
def get_history() -> list[HistoryItem]:
    items: list[HistoryItem] = []
    for record in load_history():
        try:
            items.append(HistoryItem(**record))
        except Exception:
            continue
    return items


@app.get("/api/models", response_model=ModelsResponse)
def get_models() -> ModelsResponse:
    """모델별 가격 정보 조회"""
    model_descriptions = {
        "gpt-5.4": "고품질 모델 - 소개글/세계관 생성용",
        "gpt-5": "중간 성능 모델",
        "gpt-5-mini": "경량 모델 - 데이터 수집/교차 검증용",
        "gpt-5-nano": "초경량 모델 - 비용 최소화용",
        "gpt-5-codex": "코드 생성 특화 모델",
        "gpt-5.1-codex": "고급 코드 생성 모델",
        "gpt-5.1-codex-mini": "경량 코드 생성 모델",
    }

    models = []
    pricing_table = []
    for model_name, prices in MODEL_PRICING_PER_1M_TOKENS.items():
        models.append(
            ModelPriceInfo(
                model=model_name,
                input_price=prices["input"],
                cached_input_price=prices["cached_input"],
                output_price=prices["output"],
                description=model_descriptions.get(model_name, "커스텀 모델"),
            )
        )
        pricing_table.append(
            PricingTableRow(
                model=model_name,
                input_price=prices["input"],
                cached_input_price=prices["cached_input"],
                output_price=prices["output"],
            )
        )

    return ModelsResponse(models=models, pricing_table=pricing_table)


@app.post("/api/pricing/comparison", response_model=PricingComparisonResponse)
def compare_pricing(request: PricingComparisonRequest) -> PricingComparisonResponse:
    """모델별 예상 비용 비교"""
    stage_estimates = [
        StageTokenEstimate(
            stage="데이터 수집 및 정리",
            description="Activity/Profile/Performances 초안 생성 (경량 모델 권장)",
            estimated_input_tokens=request.estimated_input_tokens,
            estimated_output_tokens=int(request.estimated_output_tokens * 0.3),
        ),
        StageTokenEstimate(
            stage="교차 검증 및 NULL 처리",
            description="정보 검증 및 NULL 판단 처리 (경량 모델 권장)",
            estimated_input_tokens=int(request.estimated_input_tokens * 0.8),
            estimated_output_tokens=int(request.estimated_output_tokens * 0.2),
        ),
        StageTokenEstimate(
            stage="소개글 및 세계관 생성",
            description="Introduction 섹션 생성 (고품질 모델 권장)",
            estimated_input_tokens=int(request.estimated_input_tokens * 0.6),
            estimated_output_tokens=int(request.estimated_output_tokens * 0.8),
        ),
    ]

    model_costs = []
    for model_name, prices in MODEL_PRICING_PER_1M_TOKENS.items():
        input_tokens = request.estimated_input_tokens
        cached_input_tokens = int(input_tokens * 0.5) if request.use_caching else 0
        non_cached_input_tokens = input_tokens - cached_input_tokens
        output_tokens = request.estimated_output_tokens

        input_cost_usd = (non_cached_input_tokens / 1_000_000) * prices["input"]
        cached_input_cost_usd = (cached_input_tokens / 1_000_000) * prices["cached_input"]
        output_cost_usd = (output_tokens / 1_000_000) * prices["output"]
        total_cost_usd = input_cost_usd + cached_input_cost_usd + output_cost_usd

        model_costs.append(
            ModelCostBreakdown(
                model=model_name,
                input_cost_usd=round(input_cost_usd, 8),
                cached_input_cost_usd=round(cached_input_cost_usd, 8),
                output_cost_usd=round(output_cost_usd, 8),
                total_cost_usd=round(total_cost_usd, 8),
            )
        )

    model_costs.sort(key=lambda x: x.total_cost_usd)
    cheapest = model_costs[0].model if model_costs else "N/A"
    most_expensive = model_costs[-1].model if model_costs else "N/A"

    return PricingComparisonResponse(
        request=request,
        stage_estimates=stage_estimates,
        model_costs=model_costs,
        cheapest_model=cheapest,
        most_expensive_model=most_expensive,
    )


@app.get("/api/samples/{file_name}", response_model=SampleResponse)
def get_sample(file_name: str) -> SampleResponse:
    sample_path = ROOT_DIR / file_name
    if sample_path.parent != ROOT_DIR or not sample_path.exists() or sample_path.suffix.lower() != ".json":
        raise HTTPException(status_code=404, detail="샘플 JSON 파일을 찾을 수 없습니다.")

    try:
        content = json.loads(read_text_file(sample_path))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"샘플 JSON 파싱에 실패했습니다: {exc}") from exc

    return SampleResponse(name=sample_path.name, content=content)


@app.post("/api/run", response_model=RunResponse)
def run_prompt(payload: RunRequest) -> RunResponse:
    client = get_client()

    artist_name = payload.artist_name.strip()
    system_prompt = payload.system_prompt
    if artist_name:
        system_prompt = system_prompt.replace("%아티스트명%", artist_name)

    started = time.perf_counter()
    try:
        selected_model, stage_models = resolve_stage_models(payload)
        shared_guardrail = (
            "\n\n최종 출력 JSON에는 출처명, URL, 마크다운 링크, 괄호형 인용, "
            "웹 검색 근거 문구를 절대 포함하지 마십시오. "
            "검색은 사실 확인 용도로만 사용하고, JSON 값은 순수한 한국어 텍스트만 남겨야 합니다."
        )

        collection_instructions = (
            f"{system_prompt}{shared_guardrail}\n\n"
            "현재 단계는 1단계: 데이터 수집 및 정리입니다.\n"
            "다음 필드만 포함한 JSON만 출력하십시오: artist_name, activity_info, profile, performances.\n"
            "introduction 필드는 절대 생성하지 마십시오.\n"
            "정보가 불확실하면 추정하지 말고 가능한 범위까지만 구조화하십시오."
        )
        collection_input = payload.user_prompt
        collection_result = execute_stage(
            client,
            stage_name="collection",
            model_name=stage_models["collection"],
            reasoning_effort=payload.reasoning_effort,
            instructions=collection_instructions,
            stage_input=collection_input,
            use_web_search=payload.use_web_search,
            json_schema=ARTIST_COLLECTION_SCHEMA,
            schema_name="artist_collection",
        )
        if not isinstance(collection_result["parsed_json"], dict):
            raise HTTPException(status_code=500, detail="1단계 결과를 JSON으로 파싱하지 못했습니다.")

        validation_instructions = (
            f"{system_prompt}{shared_guardrail}\n\n"
            "현재 단계는 2단계: 교차 검증 및 NULL 처리입니다.\n"
            "입력으로 전달된 초안 JSON을 검증하여 사실 불일치, 과장 표현, 빈 문자열을 정리하십시오.\n"
            "최종 출력은 artist_name, activity_info, profile, performances만 포함한 JSON이어야 합니다.\n"
            "검증 불가 값은 NULL 문자열 대신 JSON null로 정리하지 말고, 기존 프롬프트 규칙에 맞는 값 체계를 유지하십시오.\n"
            "introduction 필드는 절대 포함하지 마십시오."
        )
        validation_input = (
            f"{payload.user_prompt}\n\n"
            "[초안 JSON]\n"
            f"{json.dumps(collection_result['parsed_json'], ensure_ascii=False, indent=2)}"
        )
        validation_result = execute_stage(
            client,
            stage_name="validation",
            model_name=stage_models["validation"],
            reasoning_effort=payload.reasoning_effort,
            instructions=validation_instructions,
            stage_input=validation_input,
            use_web_search=payload.use_web_search,
            json_schema=ARTIST_COLLECTION_SCHEMA,
            schema_name="artist_validation",
        )
        if not isinstance(validation_result["parsed_json"], dict):
            raise HTTPException(status_code=500, detail="2단계 결과를 JSON으로 파싱하지 못했습니다.")

        introduction_instructions = (
            f"{system_prompt}{shared_guardrail}\n\n"
            "현재 단계는 3단계: introduction 생성입니다.\n"
            "검증 완료된 사실 정보만 사용하여 introduction 객체만 JSON으로 출력하십시오.\n"
            "허용 필드: summary, universe, interview.\n"
            "activity_info, profile, performances는 다시 생성하지 마십시오.\n"
            "입력으로 받은 fact 외의 새로운 사실을 추가하지 마십시오."
        )
        introduction_input = (
            f"{payload.user_prompt}\n\n"
            "[검증 완료 fact JSON]\n"
            f"{json.dumps(validation_result['parsed_json'], ensure_ascii=False, indent=2)}"
        )
        introduction_result = execute_stage(
            client,
            stage_name="introduction",
            model_name=stage_models["introduction"],
            reasoning_effort=payload.reasoning_effort,
            instructions=introduction_instructions,
            stage_input=introduction_input,
            use_web_search=False,
            json_schema=INTRODUCTION_SCHEMA,
            schema_name="artist_introduction",
        )
        if introduction_result["parsed_json"] is None:
            raise HTTPException(status_code=500, detail="3단계 결과를 JSON으로 파싱하지 못했습니다.")
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise exc
        raise HTTPException(status_code=500, detail=f"OpenAI 호출에 실패했습니다: {exc}") from exc

    duration_ms = int((time.perf_counter() - started) * 1000)
    stage_results = [collection_result, validation_result, introduction_result]
    parsed_json = merge_artist_payload(validation_result["parsed_json"], introduction_result["parsed_json"])
    output_text = json.dumps(parsed_json, ensure_ascii=False, indent=2)
    usage_payload = aggregate_usage_payload([item["usage"] for item in stage_results])
    pricing_payload = aggregate_pricing_payload([item["pricing"] for item in stage_results])
    web_sources: list[dict[str, Any]] = []
    seen_source_keys: set[str] = set()
    for stage_result in stage_results:
        for source in stage_result["web_sources"]:
            key = source.get("url") or source.get("title") or ""
            if not key or key in seen_source_keys:
                continue
            seen_source_keys.add(key)
            web_sources.append(source)
    run_id = str(uuid4())
    created_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

    history_record = {
        "run_id": run_id,
        "created_at": created_at,
        "model": selected_model,
        "stage_models": stage_models,
        "artist_name": artist_name,
        "reasoning_effort": payload.reasoning_effort,
        "use_web_search": payload.use_web_search,
        "duration_ms": duration_ms,
        "usage": usage_payload,
        "pricing": pricing_payload,
        "stage_results": stage_results,
        "web_source_count": len(web_sources),
        "output_preview": build_output_preview(output_text),
        "parsed_json": parsed_json,
    }
    append_history(history_record)

    return RunResponse(
        run_id=run_id,
        created_at=created_at,
        model=selected_model,
        stage_models=stage_models,
        artist_name=artist_name,
        reasoning_effort=payload.reasoning_effort,
        use_web_search=payload.use_web_search,
        output_text=output_text,
        parsed_json=parsed_json,
        usage=usage_payload,
        pricing=pricing_payload,
        stage_results=stage_results,
        web_sources=web_sources,
        duration_ms=duration_ms,
    )
