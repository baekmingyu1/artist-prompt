import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import ALLOWED_ORIGIN, DEFAULT_MODEL
from .schemas import (
    BootstrapResponse,
    HistoryItem,
    ModelsResponse,
    PricingComparisonRequest,
    PricingComparisonResponse,
    RunRequest,
    RunResponse,
    SampleResponse,
)
from .services.file_service import find_prompt_file, list_sample_files, load_sample_content
from .services.pricing_service import build_models_response, build_pricing_comparison_response
from .services.prompt_runner import run_prompt_pipeline
from .services.storage_service import load_history, read_text_file


app = FastAPI(title="Codex Prompt Runner")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOWED_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
        default_model=DEFAULT_MODEL,
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
    return build_models_response()


@app.post("/api/pricing/comparison", response_model=PricingComparisonResponse)
def compare_pricing(request: PricingComparisonRequest) -> PricingComparisonResponse:
    return build_pricing_comparison_response(request)


@app.get("/api/samples/{file_name}", response_model=SampleResponse)
def get_sample(file_name: str) -> SampleResponse:
    try:
        sample_path, content = load_sample_content(file_name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="샘플 JSON 파일을 찾을 수 없습니다.") from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"샘플 JSON 파싱에 실패했습니다: {exc}") from exc

    return SampleResponse(name=sample_path.name, content=content)


@app.post("/api/run", response_model=RunResponse)
def run_prompt(payload: RunRequest) -> RunResponse:
    return run_prompt_pipeline(payload)
