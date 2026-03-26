import { FormEvent, useEffect, useState } from "react";

type BootstrapResponse = {
  prompt_file_name: string | null;
  system_prompt: string;
  sample_files: string[];
  default_model: string;
};

type SampleResponse = {
  name: string;
  content: unknown;
};

type RunResponse = {
  run_id: string;
  created_at: string;
  model: string;
  artist_name: string;
  reasoning_effort: string;
  use_web_search: boolean;
  output_text: string;
  parsed_json: unknown | null;
  usage: {
    input_tokens: number;
    cached_input_tokens: number;
    output_tokens: number;
    reasoning_tokens: number;
    total_tokens: number;
  };
  pricing: {
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
    };
  };
  web_sources: {
    type?: string | null;
    title?: string | null;
    url?: string | null;
  }[];
  duration_ms: number;
};

type HistoryItem = {
  run_id: string;
  created_at: string;
  model: string;
  artist_name: string;
  reasoning_effort: string;
  use_web_search: boolean;
  duration_ms: number;
  usage: RunResponse["usage"];
  pricing: RunResponse["pricing"];
  output_preview: string;
  parsed_json: unknown | null;
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

const DEFAULT_USER_PROMPT = [
  "위 시스템 프롬프트 규칙에 맞춰 최종 결과를 JSON으로 출력해줘.",
].join("\n");

type ArtistJson = {
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

function prettyJson(value: unknown): string {
  if (!value) {
    return "";
  }
  return JSON.stringify(value, null, 2);
}

function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "-";
  }
  return new Intl.NumberFormat("ko-KR").format(value);
}

function formatUsd(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "계산 불가";
  }
  return `$${value.toFixed(6)}`;
}

function formatDateTime(value: string): string {
  try {
    return new Intl.DateTimeFormat("ko-KR", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }).format(new Date(value));
  } catch {
    return value;
  }
}

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function createPreviewHtml(data: ArtistJson): string {
  const formatDate = (value?: string) => {
    if (!value || value === "NULL") return "-";
    const matched = value.match(/^(\d{4})(\d{2})(\d{2})$/);
    if (!matched) return value;
    return `${matched[1]}.${matched[2]}.${matched[3]}`;
  };

  const normalizeText = (value?: string) => {
    if (!value || value === "NULL") return "-";
    return escapeHtml(String(value)).replaceAll("\n", "<br />");
  };

  const profileRows = [
    ["아티스트명", data.artist_name ?? "-"],
    ["실명", data.profile?.real_name ?? "-"],
    ["생년월일", formatDate(data.profile?.birth_date)],
    ["MBTI", data.profile?.mbti ?? "-"],
    ["국적", data.profile?.nationality ?? "-"],
  ]
    .map(([label, value]) => `<tr><th>${escapeHtml(label)}</th><td>${escapeHtml(String(value || "-"))}</td></tr>`)
    .join("");

  const performances = (data.performances ?? [])
    .map((item) => {
      const period =
        item.start_date === item.end_date
          ? formatDate(item.start_date)
          : `${formatDate(item.start_date)} - ${formatDate(item.end_date)}`;

      return [
        "<div class='timeline-item'>",
        `<div><span class='badge'>${escapeHtml(item.type ?? "-")}</span></div>`,
        `<div class='date'>${escapeHtml(period)}</div>`,
        `<div><strong>${escapeHtml(item.title ?? "-")}</strong></div>`,
        "</div>",
      ].join("");
    })
    .join("");

  return `<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>${escapeHtml(data.artist_name ?? "Artist Preview")}</title>
  <style>
    :root {
      --bg: #f4f7fb;
      --panel: #ffffff;
      --line: #d7dfeb;
      --text: #1d2733;
      --subtle: #5d6b7b;
      --point: #0f766e;
      --point-soft: #d8f3f0;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Pretendard", "Noto Sans KR", sans-serif;
      background:
        radial-gradient(circle at top right, rgba(15, 118, 110, 0.10), transparent 22%),
        linear-gradient(180deg, #eef4fb 0%, #f7f9fc 100%);
      color: var(--text);
    }
    .wrap { max-width: 1120px; margin: 0 auto; padding: 40px 20px 80px; }
    .hero {
      background: linear-gradient(135deg, #0f766e 0%, #155e75 100%);
      color: #fff;
      border-radius: 24px;
      padding: 32px;
      box-shadow: 0 20px 60px rgba(15, 118, 110, 0.18);
    }
    .eyebrow {
      display: inline-block;
      padding: 6px 10px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.14);
      font-size: 12px;
      letter-spacing: 0.04em;
    }
    h1, h2, h3, p { margin: 0; }
    .hero h1 { margin-top: 16px; font-size: 36px; line-height: 1.2; }
    .hero p { margin-top: 14px; max-width: 820px; line-height: 1.7; color: rgba(255, 255, 255, 0.92); }
    .grid { display: grid; gap: 20px; margin-top: 24px; grid-template-columns: repeat(12, minmax(0, 1fr)); }
    .card {
      grid-column: span 12;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 20px;
      padding: 24px;
      box-shadow: 0 10px 30px rgba(20, 34, 51, 0.06);
    }
    .card h2 { font-size: 20px; margin-bottom: 16px; }
    .meta { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-top: 24px; }
    .meta-item {
      background: rgba(255, 255, 255, 0.12);
      border: 1px solid rgba(255, 255, 255, 0.12);
      border-radius: 18px;
      padding: 16px;
    }
    .meta-item dt { font-size: 12px; color: rgba(255, 255, 255, 0.75); margin-bottom: 8px; }
    .meta-item dd { margin: 0; font-size: 18px; font-weight: 700; }
    .info-table { width: 100%; border-collapse: collapse; font-size: 14px; }
    .info-table th, .info-table td {
      border-bottom: 1px solid var(--line);
      padding: 14px 10px;
      text-align: left;
      vertical-align: top;
    }
    .info-table th { width: 160px; color: var(--subtle); font-weight: 600; }
    .text-block { line-height: 1.8; }
    .timeline { display: grid; gap: 12px; }
    .timeline-item {
      display: grid;
      grid-template-columns: 120px 160px 1fr;
      gap: 16px;
      align-items: start;
      padding: 16px;
      border: 1px solid var(--line);
      border-radius: 16px;
      background: #fbfdff;
    }
    .badge {
      display: inline-block;
      padding: 7px 10px;
      border-radius: 999px;
      background: var(--point-soft);
      color: var(--point);
      font-size: 12px;
      font-weight: 700;
    }
    .date { font-weight: 700; color: var(--text); }
    .sub { margin-top: 6px; font-size: 13px; color: var(--subtle); }
    .two-col { grid-column: span 6; }
    .full { grid-column: span 12; }
    .code {
      margin-top: 24px;
      background: #0f172a;
      color: #dbeafe;
      border-radius: 20px;
      padding: 20px;
      overflow: auto;
      font-size: 13px;
      line-height: 1.6;
      white-space: pre-wrap;
      word-break: break-word;
    }
    @media (max-width: 920px) {
      .meta, .timeline-item { grid-template-columns: 1fr; }
      .two-col { grid-column: span 12; }
      .hero h1 { font-size: 28px; }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <section class="hero">
      <span class="eyebrow">JSON 웹 미리보기</span>
      <h1>${escapeHtml(data.artist_name ?? "이름 없음")}</h1>
      <p>${normalizeText(data.introduction?.summary)}</p>
      <dl class="meta">
        <div class="meta-item">
          <dt>데뷔일</dt>
          <dd>${escapeHtml(formatDate(data.activity_info?.debut_date))}</dd>
        </div>
        <div class="meta-item">
          <dt>데뷔곡</dt>
          <dd>${escapeHtml(data.activity_info?.debut_song ?? "-")}</dd>
        </div>
        <div class="meta-item">
          <dt>활동 시기</dt>
          <dd>${escapeHtml((data.activity_info?.activity_era ?? []).join(", ") || "-")}</dd>
        </div>
        <div class="meta-item">
          <dt>국적</dt>
          <dd>${escapeHtml(data.profile?.nationality ?? "-")}</dd>
        </div>
      </dl>
    </section>

    <section class="grid">
      <article class="card two-col">
        <h2>기본 프로필</h2>
        <table class="info-table">
          <tbody>${profileRows}</tbody>
        </table>
      </article>

      <article class="card two-col">
        <h2>세계관 / 인터뷰 톤</h2>
        <div class="text-block">${normalizeText(data.introduction?.universe)}</div>
        <div class="sub" style="margin-top: 18px;">대표 메시지</div>
        <div class="text-block" style="margin-top: 8px;">${normalizeText(data.introduction?.interview)}</div>
      </article>

      <article class="card full">
        <h2>주요 공연 이력</h2>
        <div class="timeline">${performances || "<div class='sub'>공연 정보가 없습니다.</div>"}</div>
      </article>

      <article class="card full">
        <h2>원본 JSON 느낌</h2>
        <pre class="code">${escapeHtml(JSON.stringify(data, null, 2))}</pre>
      </article>
    </section>
  </div>
</body>
</html>`;
}

export default function App() {
  const [systemPrompt, setSystemPrompt] = useState("");
  const [userPrompt, setUserPrompt] = useState(DEFAULT_USER_PROMPT);
  const [artistName, setArtistName] = useState("투어스");
  const [model, setModel] = useState("gpt-5.4");
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
          artist_name: runResult.artist_name,
          reasoning_effort: runResult.reasoning_effort,
          use_web_search: runResult.use_web_search,
          duration_ms: runResult.duration_ms,
          usage: runResult.usage,
          pricing: runResult.pricing,
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

    openPreviewFromJson(result.parsed_json as ArtistJson);
  };

  const openPreviewFromJson = (json: ArtistJson) => {
    const previewHtml = createPreviewHtml(json);
    const blob = new Blob([previewHtml], { type: "text/html;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  const handleOpenHistoryPreview = (item: HistoryItem) => {
    if (!item.parsed_json || typeof item.parsed_json !== "object") {
      setError("이 실행 이력에는 HTML로 열 수 있는 JSON이 저장되어 있지 않습니다.");
      return;
    }

    openPreviewFromJson(item.parsed_json as ArtistJson);
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
              <input value={model} onChange={(event) => setModel(event.target.value)} placeholder="예: gpt-5.4" />
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
              <h3>비용 계산 상세</h3>
              <div className="pricing-grid">
                <div>
                  <span>입력 비용</span>
                  <strong>{formatUsd(result.pricing.input_cost_usd)}</strong>
                </div>
                <div>
                  <span>캐시 입력 비용</span>
                  <strong>{formatUsd(result.pricing.cached_input_cost_usd)}</strong>
                </div>
                <div>
                  <span>출력 비용</span>
                  <strong>{formatUsd(result.pricing.output_cost_usd)}</strong>
                </div>
                <div>
                  <span>가격 기준</span>
                  <strong>{result.pricing.price_reference}</strong>
                </div>
              </div>
            </section>
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
                      </div>
                      <button
                        type="button"
                        className="secondary-button"
                        onClick={() => handleOpenHistoryPreview(item)}
                        disabled={!item.parsed_json}
                      >
                        HTML 보기
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
