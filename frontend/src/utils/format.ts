const STAGE_LABELS: Record<string, string> = {
  collection: "수집/정리",
  validation: "검증/정리",
  introduction: "소개글 생성",
};

export function prettyJson(value: unknown): string {
  if (!value) {
    return "";
  }

  return JSON.stringify(value, null, 2);
}

export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "-";
  }

  return new Intl.NumberFormat("ko-KR").format(value);
}

export function formatUsd(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "계산 불가";
  }

  return `$${value.toFixed(6)}`;
}

export function formatDateTime(value: string): string {
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

export function formatStageLabel(value: string): string {
  return STAGE_LABELS[value] ?? value;
}
