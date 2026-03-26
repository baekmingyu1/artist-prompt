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
    artist_name: str
    reasoning_effort: str
    use_web_search: bool
    output_text: str
    parsed_json: Any | None
    usage: dict[str, Any]
    pricing: dict[str, Any]
    web_sources: list[dict[str, Any]]
    duration_ms: int


class HistoryItem(BaseModel):
    run_id: str
    created_at: str
    model: str
    artist_name: str
    reasoning_effort: str
    use_web_search: bool = False
    duration_ms: int
    usage: dict[str, Any]
    pricing: dict[str, Any]
    web_source_count: int = 0
    output_preview: str
    parsed_json: Any | None = None


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
            "artist_name": record.get("artist_name", ""),
            "reasoning_effort": record.get("reasoning_effort", "medium"),
            "use_web_search": record.get("use_web_search", False),
            "duration_ms": record.get("duration_ms", 0),
            "usage": record.get("usage", {}),
            "pricing": record.get("pricing", {}),
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
        instructions = system_prompt
        if payload.use_web_search:
            instructions += (
                "\n\n최종 출력 JSON에는 출처명, URL, 마크다운 링크, 괄호형 인용, "
                "웹 검색 근거 문구를 절대 포함하지 마십시오. "
                "검색은 사실 확인 용도로만 사용하고, JSON 값은 순수한 한국어 텍스트만 남겨야 합니다."
            )
        tools = [{"type": "web_search"}] if payload.use_web_search else []
        response = client.responses.create(
            model=payload.model,
            reasoning={"effort": payload.reasoning_effort},
            instructions=instructions,
            input=payload.user_prompt,
            tools=tools,
            tool_choice="auto" if tools else None,
            include=["web_search_call.action.sources"] if tools else None,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"OpenAI 호출에 실패했습니다: {exc}") from exc

    duration_ms = int((time.perf_counter() - started) * 1000)
    output_text = getattr(response, "output_text", "") or ""
    parsed_json = parse_json_text(output_text)
    if parsed_json is not None:
        parsed_json = sanitize_json_strings(parsed_json)
    usage_payload = build_usage_payload(response)
    pricing_payload = build_pricing_payload(payload.model, usage_payload)
    web_sources = extract_web_sources(response)
    run_id = str(uuid4())
    created_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

    history_record = {
        "run_id": run_id,
        "created_at": created_at,
        "model": payload.model,
        "artist_name": artist_name,
        "reasoning_effort": payload.reasoning_effort,
        "use_web_search": payload.use_web_search,
        "duration_ms": duration_ms,
        "usage": usage_payload,
        "pricing": pricing_payload,
        "web_source_count": len(web_sources),
        "output_preview": build_output_preview(output_text),
        "parsed_json": parsed_json,
    }
    append_history(history_record)

    return RunResponse(
        run_id=run_id,
        created_at=created_at,
        model=payload.model,
        artist_name=artist_name,
        reasoning_effort=payload.reasoning_effort,
        use_web_search=payload.use_web_search,
        output_text=output_text,
        parsed_json=parsed_json,
        usage=usage_payload,
        pricing=pricing_payload,
        web_sources=web_sources,
        duration_ms=duration_ms,
    )
