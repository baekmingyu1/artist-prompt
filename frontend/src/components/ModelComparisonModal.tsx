import { formatNumber, formatStageLabel, formatUsd } from "../utils/format";
import type { HistoryItem, PricingComparisonResponse, RunResponse } from "../types";

type ModelComparisonModalProps = {
  comparisonReference: RunResponse | HistoryItem | null;
  modelComparison: PricingComparisonResponse | null;
  onClose: () => void;
};

export function ModelComparisonModal({
  comparisonReference,
  modelComparison,
  onClose,
}: ModelComparisonModalProps) {
  if (!modelComparison) {
    return null;
  }

  return (
    <section className="comparison-modal-overlay">
      <div className="comparison-modal">
        <div className="comparison-modal-header">
          <h2>실사용 모델 비용 정보</h2>
          <button
            type="button"
            className="comparison-close-button"
            onClick={onClose}
          >
            ✕
          </button>
        </div>

        {comparisonReference ? (
          <div className="comparison-summary">
            <h3>실사용 결과 (모델: {comparisonReference.model})</h3>
            <div className="comparison-summary-grid">
              <div><strong>입력 토큰</strong><br />{formatNumber(comparisonReference.usage.input_tokens)}</div>
              <div><strong>캐시 입력</strong><br />{formatNumber(comparisonReference.usage.cached_input_tokens)}</div>
              <div><strong>출력 토큰</strong><br />{formatNumber(comparisonReference.usage.output_tokens)}</div>
              <div><strong>총 토큰</strong><br />{formatNumber(comparisonReference.usage.total_tokens)}</div>
              <div><strong>총 비용</strong><br />{formatUsd(comparisonReference.pricing.estimated_cost_usd)}</div>
            </div>
          </div>
        ) : (
          <p>실행 결과가 없습니다.</p>
        )}

        {comparisonReference?.stage_results?.length ? (
          <div className="comparison-section">
            <h3>실제 실행 단계별 상세</h3>
            <div className="comparison-table-wrap">
              <table className="comparison-table">
                <thead>
                  <tr>
                    <th>단계</th>
                    <th>실행 모델</th>
                    <th className="align-right">입력</th>
                    <th className="align-right">캐시 입력</th>
                    <th className="align-right">출력</th>
                    <th className="align-right">총 토큰</th>
                    <th className="align-right">예상 비용</th>
                  </tr>
                </thead>
                <tbody>
                  {comparisonReference.stage_results.map((stage) => (
                    <tr key={`${comparisonReference.run_id}-${stage.stage}`}>
                      <td>{formatStageLabel(stage.stage)}</td>
                      <td>{stage.model}</td>
                      <td className="align-right">{formatNumber(stage.usage.input_tokens)}</td>
                      <td className="align-right">{formatNumber(stage.usage.cached_input_tokens)}</td>
                      <td className="align-right">{formatNumber(stage.usage.output_tokens)}</td>
                      <td className="align-right">{formatNumber(stage.usage.total_tokens)}</td>
                      <td className="align-right">{formatUsd(stage.pricing.estimated_cost_usd)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : null}

        <div className="comparison-section">
          <h3>대체 실행 시나리오 비교</h3>
          <div className="comparison-table-wrap">
            <table className="comparison-table">
              <thead>
                <tr>
                  <th>시나리오</th>
                  <th className="align-right">입력 비용</th>
                  <th className="align-right">캐시 입력 비용</th>
                  <th className="align-right">출력 비용</th>
                  <th className="align-right">총 비용</th>
                </tr>
              </thead>
              <tbody>
                {comparisonReference ? (
                  <tr>
                    <td>실제 실행 조합 ({comparisonReference.model})</td>
                    <td className="align-right">{formatUsd(comparisonReference.pricing.input_cost_usd)}</td>
                    <td className="align-right">{formatUsd(comparisonReference.pricing.cached_input_cost_usd)}</td>
                    <td className="align-right">{formatUsd(comparisonReference.pricing.output_cost_usd)}</td>
                    <td className="align-right emphasis">{formatUsd(comparisonReference.pricing.estimated_cost_usd)}</td>
                  </tr>
                ) : null}
                {modelComparison.model_costs.map((item) => (
                  <tr key={item.model}>
                    <td>전부 {item.model}로 실행</td>
                    <td className="align-right">{formatUsd(item.input_cost_usd)}</td>
                    <td className="align-right">{formatUsd(item.cached_input_cost_usd)}</td>
                    <td className="align-right">{formatUsd(item.output_cost_usd)}</td>
                    <td className="align-right">{formatUsd(item.total_cost_usd)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="comparison-note">
          <strong>안내</strong>
          <p>
            실제 실행 조합 행은 이번 실행에서 단계별 모델을 나눠 사용한 실측 합계입니다.
            아래 단일 모델 행들은 같은 토큰 규모를 기준으로 전체를 한 모델로 돌렸다고 가정한 비교값입니다.
          </p>
        </div>

        <div className="comparison-footer">
          <button
            type="button"
            className="secondary-button"
            onClick={onClose}
          >
            닫기
          </button>
        </div>
      </div>
    </section>
  );
}
