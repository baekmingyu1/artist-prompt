import type { ArtistJson } from "../types";

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

export function createPreviewHtml(data: ArtistJson): string {
  const formatDate = (value?: string) => {
    if (!value || value === "NULL") {
      return "-";
    }

    const matched = value.match(/^(\d{4})(\d{2})(\d{2})$/);
    if (!matched) {
      return value;
    }

    return `${matched[1]}.${matched[2]}.${matched[3]}`;
  };

  const normalizeText = (value?: string) => {
    if (!value || value === "NULL") {
      return "-";
    }

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

export function createPreviewFileName(artistName?: string): string {
  const baseName = (artistName || "artist-preview")
    .trim()
    .replace(/[<>:"/\\|?*\x00-\x1F]/g, "-")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");

  return `${baseName || "artist-preview"}-preview.html`;
}

function triggerPreviewDownload(url: string, options: { download?: string; target?: string; rel?: string } = {}) {
  const link = document.createElement("a");
  link.href = url;
  if (options.download) {
    link.download = options.download;
  }
  if (options.target) {
    link.target = options.target;
  }
  if (options.rel) {
    link.rel = options.rel;
  }
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

export function openPreviewWindow(json: ArtistJson): void {
  const previewHtml = createPreviewHtml(json);
  const blob = new Blob([previewHtml], { type: "text/html;charset=utf-8" });
  const url = URL.createObjectURL(blob);

  triggerPreviewDownload(url, {
    target: "_blank",
    rel: "noopener noreferrer",
  });

  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function downloadPreviewFile(json: ArtistJson): void {
  const previewHtml = createPreviewHtml(json);
  const blob = new Blob([previewHtml], { type: "text/html;charset=utf-8" });
  const url = URL.createObjectURL(blob);

  triggerPreviewDownload(url, {
    download: createPreviewFileName(json.artist_name),
  });

  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
