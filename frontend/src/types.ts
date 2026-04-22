export type BootstrapResponse = {
  prompt_file_name: string | null;
  system_prompt: string;
  sample_files: string[];
  default_model: string;
};

export type SampleResponse = {
  name: string;
  content: unknown;
};

export type UsagePayload = {
  input_tokens: number;
  cached_input_tokens: number;
  output_tokens: number;
  reasoning_tokens: number;
  total_tokens: number;
};

export type PricingPayload = {
  currency: string;
  estimated_cost_usd: number | null;
  estimated_cost_krw: number | null;
  input_cost_usd: number | null;
  cached_input_cost_usd: number | null;
  output_cost_usd: number | null;
  price_reference: string;
  price_table?: {
    input: number;
    cached_input: number;
    output: number;
  } | null;
};

export type WebSource = {
  type?: string | null;
  title?: string | null;
  url?: string | null;
};

export type StageResult = {
  stage: string;
  model: string;
  duration_ms: number;
  output_text: string;
  parsed_json: unknown | null;
  usage: UsagePayload;
  pricing: PricingPayload;
  web_sources: WebSource[];
};

export type RunResponse = {
  run_id: string;
  created_at: string;
  model: string;
  stage_models: Record<string, string>;
  artist_name: string;
  reasoning_effort: string;
  use_web_search: boolean;
  output_text: string;
  parsed_json: unknown | null;
  usage: UsagePayload;
  pricing: PricingPayload;
  stage_results: StageResult[];
  web_sources: WebSource[];
  duration_ms: number;
};

export type StageTokenEstimate = {
  stage: string;
  description: string;
  estimated_input_tokens: number;
  estimated_output_tokens: number;
};

export type PricingComparisonRequest = {
  estimated_input_tokens: number;
  estimated_output_tokens: number;
  use_caching: boolean;
};

export type ModelCostBreakdown = {
  model: string;
  input_cost_usd: number;
  cached_input_cost_usd: number;
  output_cost_usd: number;
  total_cost_usd: number;
};

export type PricingComparisonResponse = {
  request: PricingComparisonRequest;
  stage_estimates: StageTokenEstimate[];
  model_costs: ModelCostBreakdown[];
  cheapest_model: string;
  most_expensive_model: string;
};

export type HistoryItem = {
  run_id: string;
  created_at: string;
  model: string;
  stage_models: Record<string, string>;
  artist_name: string;
  reasoning_effort: string;
  use_web_search: boolean;
  duration_ms: number;
  usage: UsagePayload;
  pricing: PricingPayload;
  stage_results: StageResult[];
  web_source_count: number;
  output_preview: string;
  parsed_json: unknown | null;
};

export type ArtistJson = {
  artist_name?: string;
  activity_info?: {
    debut_date?: string;
    debut_song?: string;
    activity_era?: string[];
  };
  introduction?: {
    summary?: string;
    universe?: string;
    interview?: string;
  };
  profile?: {
    real_name?: string;
    birth_date?: string;
    mbti?: string;
    nationality?: string;
  };
  performances?: Array<{
    type?: string;
    start_date?: string;
    end_date?: string;
    title?: string;
  }>;
};
