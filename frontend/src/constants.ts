export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export const DEFAULT_USER_PROMPT = "위 시스템 프롬프트 규칙에 맞춰 최종 결과를 JSON으로 출력해줘.";

export function getDefaultStageModels(model: string): Record<string, string> {
  if (model === "auto") {
    return {
      collection: "gpt-5-mini",
      validation: "gpt-5-mini",
      introduction: "gpt-5.4",
    };
  }

  return {
    collection: model,
    validation: model,
    introduction: model,
  };
}
