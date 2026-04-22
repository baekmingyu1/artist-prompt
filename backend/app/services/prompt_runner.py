import json
import os
import re
import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from openai import OpenAI

from ..prompt_assets import ARTIST_COLLECTION_SCHEMA, INTRODUCTION_SCHEMA
from ..schemas import RunRequest, RunResponse
from .pricing_service import (
    aggregate_pricing_payload,
    aggregate_usage_payload,
    build_pricing_payload,
    build_usage_payload,
)
from .storage_service import append_history


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


def build_stage_input(*, artist_name: str, user_prompt: str, extra_context: str | None = None) -> str:
    parts = []
    if artist_name:
        parts.append(f"[대상 아티스트]\n{artist_name}")
    parts.append(user_prompt)
    if extra_context:
        parts.append(extra_context)
    return "\n\n".join(part for part in parts if part)


def is_null_like_payload(value: Any) -> bool:
    if value == "NULL":
        return True
    if value is None:
        return True
    if isinstance(value, list):
        return len(value) == 0 or all(is_null_like_payload(item) for item in value)
    if isinstance(value, dict):
        return len(value) == 0 or all(is_null_like_payload(item) for item in value.values())
    return False


def should_retry_with_search(stage_result: dict[str, Any], *, use_web_search: bool) -> bool:
    if not use_web_search:
        return False
    if stage_result["web_sources"]:
        return False
    parsed_json = stage_result.get("parsed_json")
    return is_null_like_payload(parsed_json)


def should_retry_universe_only(stage_result: dict[str, Any], *, use_web_search: bool) -> bool:
    if not use_web_search:
        return False
    parsed_json = stage_result.get("parsed_json")
    if not isinstance(parsed_json, dict):
        return False
    universe_value = parsed_json.get("universe")
    if universe_value != "NULL":
        return False
    return len(stage_result.get("web_sources", [])) == 0


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
    response = client.responses.create(**request_kwargs)
    duration_ms = int((time.perf_counter() - started) * 1000)
    output_text = getattr(response, "output_text", "") or ""
    parsed_json = parse_json_text(output_text)
    if parsed_json is not None:
        parsed_json = sanitize_json_strings(parsed_json)

    usage_payload = build_usage_payload(response)
    pricing_payload = build_pricing_payload(model_name, usage_payload)
    return {
        "stage": stage_name,
        "model": model_name,
        "duration_ms": duration_ms,
        "output_text": output_text,
        "parsed_json": parsed_json,
        "usage": usage_payload,
        "pricing": pricing_payload,
        "web_sources": extract_web_sources(response),
    }


def execute_stage_with_search_retry(
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
    stage_result = execute_stage(
        client,
        stage_name=stage_name,
        model_name=model_name,
        reasoning_effort=reasoning_effort,
        instructions=instructions,
        stage_input=stage_input,
        use_web_search=use_web_search,
        json_schema=json_schema,
        schema_name=schema_name,
    )
    if not should_retry_with_search(stage_result, use_web_search=use_web_search):
        return stage_result

    retry_instructions = (
        f"{instructions}\n\n"
        "중요: 이번 단계에서는 반드시 웹 검색 도구를 실제로 사용하십시오.\n"
        "공식 출처 또는 허용된 검색 출처를 먼저 조회한 뒤 결과를 JSON으로 작성하십시오.\n"
        "검색 없이 추정으로 NULL만 반환하는 응답은 허용되지 않습니다.\n"
        "확인 가능한 값은 채우고, 끝까지 확인되지 않은 값만 NULL로 두십시오."
    )
    return execute_stage(
        client,
        stage_name=stage_name,
        model_name=model_name,
        reasoning_effort=reasoning_effort,
        instructions=retry_instructions,
        stage_input=stage_input,
        use_web_search=use_web_search,
        json_schema=json_schema,
        schema_name=schema_name,
    )


def execute_introduction_stage(
    client: OpenAI,
    *,
    model_name: str,
    reasoning_effort: str,
    instructions: str,
    stage_input: str,
    use_web_search: bool,
) -> dict[str, Any]:
    stage_result = execute_stage(
        client,
        stage_name="introduction",
        model_name=model_name,
        reasoning_effort=reasoning_effort,
        instructions=instructions,
        stage_input=stage_input,
        use_web_search=use_web_search,
        json_schema=INTRODUCTION_SCHEMA,
        schema_name="artist_introduction",
    )
    if not should_retry_universe_only(stage_result, use_web_search=use_web_search):
        return stage_result

    retry_instructions = (
        f"{instructions}\n\n"
        "중요: universe 필드가 NULL이면, 이번 재시도에서는 반드시 웹 검색 도구를 사용해 공식 출처와 허용된 음악/영상 출처를 다시 확인하십시오.\n"
        "뮤직비디오, 공식 소개문, 앨범 콘셉트 설명, 공식 SNS 소개, 가사나 시리즈형 콘셉트의 반복 키워드로 세계관 존재 여부를 판단하십시오.\n"
        "검증 가능한 콘셉트 구조가 보이면 universe를 작성하고, 정말 약하거나 일관된 근거가 없을 때만 NULL로 두십시오."
    )
    return execute_stage(
        client,
        stage_name="introduction",
        model_name=model_name,
        reasoning_effort=reasoning_effort,
        instructions=retry_instructions,
        stage_input=stage_input,
        use_web_search=use_web_search,
        json_schema=INTRODUCTION_SCHEMA,
        schema_name="artist_introduction",
    )


def run_prompt_pipeline(payload: RunRequest) -> RunResponse:
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

        collection_result = execute_stage_with_search_retry(
            client,
            stage_name="collection",
            model_name=stage_models["collection"],
            reasoning_effort=payload.reasoning_effort,
            instructions=(
                f"{system_prompt}{shared_guardrail}\n\n"
                "현재 단계는 1단계: 데이터 수집 및 정리입니다.\n"
                "다음 필드만 포함한 JSON만 출력하십시오: artist_name, activity_info, profile, performances.\n"
                "introduction 필드는 절대 생성하지 마십시오.\n"
                "정보가 불확실하면 추정하지 말고 가능한 범위까지만 구조화하십시오."
            ),
            stage_input=build_stage_input(
                artist_name=artist_name,
                user_prompt=payload.user_prompt,
            ),
            use_web_search=payload.use_web_search,
            json_schema=ARTIST_COLLECTION_SCHEMA,
            schema_name="artist_collection",
        )
        if not isinstance(collection_result["parsed_json"], dict):
            raise HTTPException(status_code=500, detail="1단계 결과를 JSON으로 파싱하지 못했습니다.")

        validation_result = execute_stage_with_search_retry(
            client,
            stage_name="validation",
            model_name=stage_models["validation"],
            reasoning_effort=payload.reasoning_effort,
            instructions=(
                f"{system_prompt}{shared_guardrail}\n\n"
                "현재 단계는 2단계: 교차 검증 및 NULL 처리입니다.\n"
                "입력으로 전달된 초안 JSON을 검증하여 사실 불일치, 과장 표현, 빈 문자열을 정리하십시오.\n"
                "최종 출력은 artist_name, activity_info, profile, performances만 포함한 JSON이어야 합니다.\n"
                "검증 불가 값은 NULL 문자열 대신 JSON null로 정리하지 말고, 기존 프롬프트 규칙에 맞는 값 체계를 유지하십시오.\n"
                "introduction 필드는 절대 포함하지 마십시오."
            ),
            stage_input=build_stage_input(
                artist_name=artist_name,
                user_prompt=payload.user_prompt,
                extra_context=(
                    "[초안 JSON]\n"
                    f"{json.dumps(collection_result['parsed_json'], ensure_ascii=False, indent=2)}"
                ),
            ),
            use_web_search=payload.use_web_search,
            json_schema=ARTIST_COLLECTION_SCHEMA,
            schema_name="artist_validation",
        )
        if not isinstance(validation_result["parsed_json"], dict):
            raise HTTPException(status_code=500, detail="2단계 결과를 JSON으로 파싱하지 못했습니다.")

        introduction_result = execute_introduction_stage(
            client,
            model_name=stage_models["introduction"],
            reasoning_effort=payload.reasoning_effort,
            instructions=(
                f"{system_prompt}{shared_guardrail}\n\n"
                "현재 단계는 3단계: introduction 생성입니다.\n"
                "검증 완료된 사실 정보만 사용하되, universe 필드는 필요하면 허용된 검색 출처에서 추가 확인하여 introduction 객체만 JSON으로 출력하십시오.\n"
                "허용 필드: summary, universe, interview.\n"
                "activity_info, profile, performances는 다시 생성하지 마십시오.\n"
                "summary와 interview는 입력으로 받은 fact를 중심으로 작성하십시오.\n"
                "universe는 공식 소개문, 공식 SNS, 공식 영상/뮤직비디오, 검증 가능한 플랫폼 설명에서 반복 확인되는 콘셉트가 있을 때만 작성하십시오.\n"
                "세계관 존재가 확인되는데도 단순히 정보 부족을 이유로 NULL 처리하지 마십시오.\n"
                "다만 추측성 해석, 팬 이론, 단발성 연출만으로 과장해서 쓰지 마십시오."
            ),
            stage_input=build_stage_input(
                artist_name=artist_name,
                user_prompt=payload.user_prompt,
                extra_context=(
                    "[검증 완료 fact JSON]\n"
                    f"{json.dumps(validation_result['parsed_json'], ensure_ascii=False, indent=2)}"
                ),
            ),
            use_web_search=payload.use_web_search,
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

    append_history(
        {
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
    )

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
