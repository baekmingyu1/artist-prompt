import { FormEvent, useEffect, useState } from "react";

import { ModelComparisonModal } from "./components/ModelComparisonModal";
import { API_BASE_URL, DEFAULT_USER_PROMPT, getDefaultStageModels } from "./constants";
import type {
  ArtistJson,
  BootstrapResponse,
  HistoryItem,
  PricingComparisonResponse,
  RunResponse,
  SampleResponse,
} from "./types";
import { formatDateTime, formatNumber, formatStageLabel, formatUsd, prettyJson } from "./utils/format";
import { downloadPreviewFile, openPreviewWindow } from "./utils/preview";

export default function App() {
  const [systemPrompt, setSystemPrompt] = useState("");
  const [userPrompt, setUserPrompt] = useState(DEFAULT_USER_PROMPT);
  const [artistName, setArtistName] = useState("투어스");
  const [model, setModel] = useState("gpt-5.4");
  const [stageModels, setStageModels] = useState<Record<string, string>>(getDefaultStageModels("auto"));
  const [reasoningEffort, setReasoningEffort] = useState("medium");
  const [useWebSearch, setUseWebSearch] = useState(true);
  const [sampleFiles, setSampleFiles] = useState<string[]>([]);
  const [promptFileName, setPromptFileName] = useState<string | null>(null);
  const [selectedSample, setSelectedSample] = useState("");
  const [sampleJsonText, setSampleJsonText] = useState("");
  const [result, setResult] = useState<RunResponse | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [showModelComparison, setShowModelComparison] = useState(false);
  const [modelComparison, setModelComparison] = useState<PricingComparisonResponse | null>(null);
  const [comparisonReference, setComparisonReference] = useState<RunResponse | HistoryItem | null>(null);
  const [isLoadingComparison, setIsLoadingComparison] = useState(false);

  useEffect(() => {
    const loadBootstrap = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/bootstrap`);
        if (!response.ok) {
          throw new Error("초기 데이터를 불러오지 못했습니다.");
        }

        const data: BootstrapResponse = await response.json();
        setSystemPrompt(data.system_prompt);
        setSampleFiles(data.sample_files);
        setPromptFileName(data.prompt_file_name);
        setModel(data.default_model);
        setStageModels({
          ...getDefaultStageModels("auto"),
          introduction: data.default_model,
        });
      } catch (fetchError) {
        const message = fetchError instanceof Error ? fetchError.message : "알 수 없는 오류가 발생했습니다.";
        setError(message);
      }
    };

    const loadHistory = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/history`);
        if (!response.ok) {
          throw new Error("실행 이력을 불러오지 못했습니다.");
        }

        const data: HistoryItem[] = await response.json();
        setHistory(data);
      } catch (fetchError) {
        const message = fetchError instanceof Error ? fetchError.message : "이력 로드 중 오류가 발생했습니다.";
        setError(message);
      }
    };

    void loadBootstrap();
    void loadHistory();
  }, []);

  const handleSampleLoad = async (fileName: string) => {
    setSelectedSample(fileName);
    if (!fileName) {
      setSampleJsonText("");
      return;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/api/samples/${encodeURIComponent(fileName)}`);
      if (!response.ok) {
        throw new Error("샘플 JSON을 불러오지 못했습니다.");
      }

      const data: SampleResponse = await response.json();
      setSampleJsonText(prettyJson(data.content));
    } catch (fetchError) {
      const message = fetchError instanceof Error ? fetchError.message : "샘플 로드 중 오류가 발생했습니다.";
      setError(message);
    }
  };

  const handleModelChange = (value: string) => {
    setModel(value);
    setStageModels(getDefaultStageModels(value));
  };

  const handleStageModelChange = (stage: string, value: string) => {
    setStageModels((current) => ({
      ...current,
      [stage]: value,
    }));
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setIsLoading(true);
    setError("");

    try {
      const response = await fetch(`${API_BASE_URL}/api/run`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          system_prompt: systemPrompt,
          user_prompt: userPrompt,
          artist_name: artistName,
          model,
          stage_models: stageModels,
          reasoning_effort: reasoningEffort,
          use_web_search: useWebSearch,
        }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail ?? "실행에 실패했습니다.");
      }

      const runResult = data as RunResponse;
      setResult(runResult);
      setHistory((current) => [
        {
          run_id: runResult.run_id,
          created_at: runResult.created_at,
          model: runResult.model,
          stage_models: runResult.stage_models,
          artist_name: runResult.artist_name,
          reasoning_effort: runResult.reasoning_effort,
          use_web_search: runResult.use_web_search,
          duration_ms: runResult.duration_ms,
          usage: runResult.usage,
          pricing: runResult.pricing,
          stage_results: runResult.stage_results,
          web_source_count: runResult.web_sources.length,
          output_preview: runResult.output_text.replace(/\s+/g, " ").trim().slice(0, 180),
          parsed_json: runResult.parsed_json,
        },
        ...current,
      ].slice(0, 100));
    } catch (fetchError) {
      const message = fetchError instanceof Error ? fetchError.message : "실행 중 오류가 발생했습니다.";
      setError(message);
      setResult(null);
    } finally {
      setIsLoading(false);
    }
  };

  const handleOpenPreview = () => {
    if (!result?.parsed_json || typeof result.parsed_json !== "object") {
      setError("미리보기로 열 수 있는 JSON 결과가 없습니다.");
      return;
    }

    openPreviewWindow(result.parsed_json as ArtistJson);
  };

  const handleDownloadPreview = () => {
    if (!result?.parsed_json || typeof result.parsed_json !== "object") {
      setError("다운로드할 HTML 결과가 없습니다.");
      return;
    }

    downloadPreviewFile(result.parsed_json as ArtistJson);
  };

  const handleOpenHistoryPreview = (item: HistoryItem) => {
    if (!item.parsed_json || typeof item.parsed_json !== "object") {
      setError("이 실행 이력에는 HTML로 열 수 있는 JSON이 저장되어 있지 않습니다.");
      return;
    }

    openPreviewWindow(item.parsed_json as ArtistJson);
  };

  const handleDownloadHistoryPreview = (item: HistoryItem) => {
    if (!item.parsed_json || typeof item.parsed_json !== "object") {
      setError("이 실행 이력에는 다운로드할 HTML 결과가 저장되어 있지 않습니다.");
      return;
    }

    downloadPreviewFile(item.parsed_json as ArtistJson);
  };

  const handleShowModelComparison = async (source?: RunResponse | HistoryItem) => {
    setShowModelComparison(true);
    setIsLoadingComparison(true);
    const selectedResult = source || result;
    setComparisonReference(selectedResult ?? null);

    try {
      if (!selectedResult) {
        throw new Error("비교할 실행 데이터가 없습니다.");
      }
      const estimatedInput = selectedResult.usage.input_tokens || 5000;
      const estimatedOutput = selectedResult.usage.output_tokens || 2000;

      const response = await fetch(`${API_BASE_URL}/api/pricing/comparison`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          estimated_input_tokens: estimatedInput,
          estimated_output_tokens: estimatedOutput,
          use_caching: true,
        }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail ?? "모델 비교를 불러올 수 없습니다.");
      }

      setModelComparison(data as PricingComparisonResponse);
    } catch (fetchError) {
      const message = fetchError instanceof Error ? fetchError.message : "모델 비교 로드 중 오류가 발생했습니다.";
      setError(message);
    } finally {
      setIsLoadingComparison(false);
    }
  };

  return (
    <main className="page-shell">
      <section className="hero-panel">
        <div>
          <p className="eyebrow">Codex API Test Console</p>
          <h1>시스템 프롬프트 실행용 테스트 웹</h1>
          <p className="hero-copy">
            로컬 시스템 프롬프트를 바로 불러와서 편집하고, 아티스트명 치환값과 사용자 프롬프트를 함께 실행할 수 있습니다.
            결과는 원문과 JSON 파싱 결과를 동시에 확인하도록 구성했습니다.
          </p>
        </div>
        <dl className="hero-metrics">
          <div>
            <dt>프롬프트 파일</dt>
            <dd>{promptFileName ?? "없음"}</dd>
          </div>
          <div>
            <dt>기본 모델</dt>
            <dd>{model}</dd>
          </div>
          <div>
            <dt>샘플 JSON</dt>
            <dd>{sampleFiles.length}개</dd>
          </div>
        </dl>
      </section>

      <section className="layout-grid">
        <form className="panel panel-form" onSubmit={handleSubmit}>
          <div className="panel-head">
            <h2>실행 설정</h2>
            <button type="submit" className="primary-button" disabled={isLoading}>
              {isLoading ? "실행 중..." : "Prompt 실행"}
            </button>
          </div>

          <div className="control-row">
            <label>
              <span>아티스트명</span>
              <input value={artistName} onChange={(event) => setArtistName(event.target.value)} placeholder="예: 트와이스" />
            </label>
            <label>
              <span>모델</span>
              <select value={model} onChange={(event) => handleModelChange(event.target.value)}>
                <option value="auto">auto (프롬프트 기반 자동 선택)</option>
                <option value="gpt-5.4">gpt-5.4 (고품질)</option>
                <option value="gpt-5">gpt-5</option>
                <option value="gpt-5-mini">gpt-5-mini</option>
                <option value="gpt-5-nano">gpt-5-nano</option>
              </select>
              <small style={{ color: "#666" }}>auto 선택 시 수집/검증은 gpt-5-mini, 소개글은 gpt-5.4로 3단계 분리 실행됩니다.</small>
            </label>
            <label>
              <span>Reasoning</span>
              <select value={reasoningEffort} onChange={(event) => setReasoningEffort(event.target.value)}>
                <option value="low">low</option>
                <option value="medium">medium</option>
                <option value="high">high</option>
              </select>
            </label>
          </div>

          <div className="control-row">
            <label>
              <span>수집/정리 모델</span>
              <select value={stageModels.collection} onChange={(event) => handleStageModelChange("collection", event.target.value)}>
                <option value="gpt-5.4">gpt-5.4</option>
                <option value="gpt-5">gpt-5</option>
                <option value="gpt-5-mini">gpt-5-mini</option>
                <option value="gpt-5-nano">gpt-5-nano</option>
              </select>
            </label>
            <label>
              <span>검증/정리 모델</span>
              <select value={stageModels.validation} onChange={(event) => handleStageModelChange("validation", event.target.value)}>
                <option value="gpt-5.4">gpt-5.4</option>
                <option value="gpt-5">gpt-5</option>
                <option value="gpt-5-mini">gpt-5-mini</option>
                <option value="gpt-5-nano">gpt-5-nano</option>
              </select>
            </label>
            <label>
              <span>소개글 모델</span>
              <select value={stageModels.introduction} onChange={(event) => handleStageModelChange("introduction", event.target.value)}>
                <option value="gpt-5.4">gpt-5.4</option>
                <option value="gpt-5">gpt-5</option>
                <option value="gpt-5-mini">gpt-5-mini</option>
                <option value="gpt-5-nano">gpt-5-nano</option>
              </select>
            </label>
          </div>

          <label className="toggle-field">
            <input
              type="checkbox"
              checked={useWebSearch}
              onChange={(event) => setUseWebSearch(event.target.checked)}
            />
            <span>웹 검색 사용</span>
            <small>공연 정보처럼 최신 데이터가 필요한 경우 켜두는 편이 맞습니다.</small>
          </label>

          <label className="field">
            <span>System Prompt</span>
            <textarea
              value={systemPrompt}
              onChange={(event) => setSystemPrompt(event.target.value)}
              rows={20}
            />
          </label>

          <label className="field">
            <span>User Prompt</span>
            <textarea
              value={userPrompt}
              onChange={(event) => setUserPrompt(event.target.value)}
              rows={8}
            />
          </label>
        </form>

        <section className="panel panel-side">
          <div className="panel-head">
            <h2>샘플 기준값</h2>
          </div>

          <label className="field">
            <span>샘플 JSON 선택</span>
            <select value={selectedSample} onChange={(event) => void handleSampleLoad(event.target.value)}>
              <option value="">선택 안 함</option>
              {sampleFiles.map((file) => (
                <option value={file} key={file}>
                  {file}
                </option>
              ))}
            </select>
          </label>

          <div className="code-panel">
            <pre>{sampleJsonText || "샘플 JSON을 선택하면 이 영역에 기준 결과가 표시됩니다."}</pre>
          </div>
        </section>

        <section className="panel panel-result">
          <div className="panel-head">
            <h2>실행 결과</h2>
            <div className="result-actions">
              {result ? (
                <p className="meta-chip">
                  {result.model} / {result.reasoning_effort} / {result.duration_ms}ms
                </p>
              ) : null}
              <button
                type="button"
                className="secondary-button"
                onClick={handleOpenPreview}
                disabled={!result?.parsed_json}
              >
                HTML 보기
              </button>
              <button
                type="button"
                className="secondary-button"
                onClick={handleDownloadPreview}
                disabled={!result?.parsed_json}
              >
                HTML 다운로드
              </button>
            </div>
          </div>

          {error ? <div className="error-box">{error}</div> : null}

          {result ? (
            <section className="stats-grid">
              <article className="stat-card">
                <span>총 토큰</span>
                <strong>{formatNumber(result.usage.total_tokens)}</strong>
              </article>
              <article className="stat-card">
                <span>입력 토큰</span>
                <strong>{formatNumber(result.usage.input_tokens)}</strong>
                <small>캐시 제외 기준</small>
              </article>
              <article className="stat-card">
                <span>캐시 입력 토큰</span>
                <strong>{formatNumber(result.usage.cached_input_tokens)}</strong>
              </article>
              <article className="stat-card">
                <span>출력 토큰</span>
                <strong>{formatNumber(result.usage.output_tokens)}</strong>
              </article>
              <article className="stat-card">
                <span>Reasoning 토큰</span>
                <strong>{formatNumber(result.usage.reasoning_tokens)}</strong>
              </article>
              <article className="stat-card accent">
                <span>예상 비용</span>
                <strong>{formatUsd(result.pricing.estimated_cost_usd)}</strong>
                <small>USD 추정치</small>
              </article>
            </section>
          ) : null}

          {result ? (
            <section className="pricing-panel">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
                <h3 style={{ margin: 0 }}>단계별 실행</h3>
              </div>
              <div className="pricing-grid">
                {result.stage_results.map((stage) => (
                  <div key={stage.stage}>
                    <span>{formatStageLabel(stage.stage)}</span>
                    <strong>{stage.model}</strong>
                    <small>
                      {formatNumber(stage.usage.total_tokens)} tokens / {formatUsd(stage.pricing.estimated_cost_usd)} / {formatNumber(stage.duration_ms)}ms
                    </small>
                  </div>
                ))}
              </div>
            </section>
          ) : null}

          {result ? (
            <section className="pricing-panel">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
                <h3 style={{ margin: 0 }}>비용 계산 상세</h3>
                <button
                  type="button"
                  className="secondary-button"
                  onClick={() => handleShowModelComparison()}
                  disabled={isLoadingComparison}
                >
                  {isLoadingComparison ? "로드 중..." : "모델 비용 비교"}
                </button>
              </div>
              <div className="pricing-grid">
                <div>
                  <span>총 토큰</span>
                  <strong>{formatNumber(result.usage.total_tokens)}</strong>
                </div>
                <div>
                  <span>입력 토큰 (비캐시)</span>
                  <strong>{formatNumber(result.usage.input_tokens - result.usage.cached_input_tokens)}</strong>
                </div>
                <div>
                  <span>캐시 입력 토큰</span>
                  <strong>{formatNumber(result.usage.cached_input_tokens)}</strong>
                </div>
                <div>
                  <span>출력 토큰</span>
                  <strong>{formatNumber(result.usage.output_tokens)}</strong>
                </div>
                <div>
                  <span>입력 비용</span>
                  <strong>{formatUsd(result.pricing.input_cost_usd)}</strong>
                </div>
                <div>
                  <span>캐시 입력 비용</span>
                  <strong>{formatUsd(result.pricing.cached_input_cost_usd)} <small>(90% 절감)</small></strong>
                </div>
                <div>
                  <span>출력 비용</span>
                  <strong>{formatUsd(result.pricing.output_cost_usd)}</strong>
                </div>
                <div>
                  <span>총 비용</span>
                  <strong>{formatUsd(result.pricing.estimated_cost_usd)}</strong>
                </div>
              </div>
            </section>
          ) : null}

          {showModelComparison ? (
            <ModelComparisonModal
              comparisonReference={comparisonReference}
              modelComparison={modelComparison}
              onClose={() => setShowModelComparison(false)}
            />
          ) : null}

          <div className="result-grid">
            <article className="result-card">
              <h3>Raw Output</h3>
              <pre>{result?.output_text || "아직 실행 결과가 없습니다."}</pre>
            </article>

            <article className="result-card">
              <h3>Parsed JSON</h3>
              <pre>{result?.parsed_json ? prettyJson(result.parsed_json) : "JSON 파싱 결과가 없습니다."}</pre>
            </article>
          </div>
        </section>

        <section className="panel panel-history">
          <div className="panel-head">
            <h2>실행 이력</h2>
            <p className="meta-chip">최근 {history.length}건</p>
          </div>

          <div className="history-list">
            {history.length === 0 ? (
              <div className="history-empty">아직 저장된 실행 이력이 없습니다.</div>
            ) : (
              history.map((item) => (
                <article className="history-card" key={item.run_id}>
                  <div className="history-top">
                    <div>
                      <h3>{item.artist_name || "아티스트명 없음"}</h3>
                      <p>{formatDateTime(item.created_at)}</p>
                    </div>
                    <div className="history-actions">
                      <div className="history-badges">
                        <span>{item.model}</span>
                        <span>{item.reasoning_effort}</span>
                        <span>{item.use_web_search ? "web on" : "web off"}</span>
                        {Object.entries(item.stage_models || {}).map(([stage, stageModel]) => (
                          <span key={`${item.run_id}-${stage}`}>{formatStageLabel(stage)}:{stageModel}</span>
                        ))}
                      </div>
                      <button
                        type="button"
                        className="secondary-button"
                        onClick={() => handleShowModelComparison(item)}
                        disabled={isLoadingComparison}
                        title="모델별 예상 비용을 비교합니다"
                      >
                        비용 비교
                      </button>
                      <button
                        type="button"
                        className="secondary-button"
                        onClick={() => handleOpenHistoryPreview(item)}
                        disabled={!item.parsed_json}
                      >
                        HTML 보기
                      </button>
                      <button
                        type="button"
                        className="secondary-button"
                        onClick={() => handleDownloadHistoryPreview(item)}
                        disabled={!item.parsed_json}
                      >
                        HTML 다운로드
                      </button>
                    </div>
                  </div>

                  <div className="history-metrics">
                    <div>
                      <span>총 토큰</span>
                      <strong>{formatNumber(item.usage.total_tokens)}</strong>
                    </div>
                    <div>
                      <span>입력</span>
                      <strong>{formatNumber(item.usage.input_tokens)}</strong>
                    </div>
                    <div>
                      <span>출력</span>
                      <strong>{formatNumber(item.usage.output_tokens)}</strong>
                    </div>
                    <div>
                      <span>예상 비용</span>
                      <strong>{formatUsd(item.pricing.estimated_cost_usd)}</strong>
                    </div>
                    <div>
                      <span>응답 시간</span>
                      <strong>{formatNumber(item.duration_ms)}ms</strong>
                    </div>
                  </div>

                  <p className="history-preview">{item.output_preview || "출력 미리보기가 없습니다."}</p>
                </article>
              ))
            )}
          </div>
        </section>
      </section>
    </main>
  );
}
