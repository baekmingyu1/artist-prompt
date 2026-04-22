from typing import Any

from ..config import MODEL_DESCRIPTIONS, MODEL_PRICING_PER_1M_TOKENS
from ..schemas import (
    ModelCostBreakdown,
    ModelPriceInfo,
    ModelsResponse,
    PricingComparisonRequest,
    PricingComparisonResponse,
    PricingTableRow,
    StageTokenEstimate,
)


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


def build_models_response() -> ModelsResponse:
    models = []
    pricing_table = []
    for model_name, prices in MODEL_PRICING_PER_1M_TOKENS.items():
        models.append(
            ModelPriceInfo(
                model=model_name,
                input_price=prices["input"],
                cached_input_price=prices["cached_input"],
                output_price=prices["output"],
                description=MODEL_DESCRIPTIONS.get(model_name, "커스텀 모델"),
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


def build_pricing_comparison_response(request: PricingComparisonRequest) -> PricingComparisonResponse:
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
