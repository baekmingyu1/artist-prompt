from typing import Any

from pydantic import BaseModel, Field

from .config import DEFAULT_MODEL


class RunRequest(BaseModel):
    system_prompt: str = Field(..., min_length=1)
    user_prompt: str = Field(..., min_length=1)
    artist_name: str = ""
    model: str = Field(default_factory=lambda: DEFAULT_MODEL)
    stage_models: dict[str, str] | None = None
    reasoning_effort: str = "medium"
    use_web_search: bool = True


class SampleResponse(BaseModel):
    name: str
    content: Any


class PriceTable(BaseModel):
    input: float
    cached_input: float
    output: float


class UsagePayload(BaseModel):
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    reasoning_tokens: int
    total_tokens: int


class PricingPayload(BaseModel):
    currency: str
    estimated_cost_usd: float | None
    estimated_cost_krw: float | None
    input_cost_usd: float | None
    cached_input_cost_usd: float | None
    output_cost_usd: float | None
    price_reference: str
    price_table: PriceTable | dict[str, float] | None = None


class WebSource(BaseModel):
    type: str | None = None
    title: str | None = None
    url: str | None = None


class StageResult(BaseModel):
    stage: str
    model: str
    duration_ms: int
    output_text: str
    parsed_json: Any | None
    usage: UsagePayload
    pricing: PricingPayload
    web_sources: list[WebSource]


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
    usage: UsagePayload
    pricing: PricingPayload
    stage_results: list[StageResult]
    web_sources: list[WebSource]
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
    usage: UsagePayload
    pricing: PricingPayload
    stage_results: list[StageResult] = Field(default_factory=list)
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
