import { AlertTriangle, CheckCircle2, FileSpreadsheet, XCircle } from "lucide-react";
import { MetricCard } from "./MetricCard";

interface MetricsGridProps {
  total: number;
  qualified: number;
  review: number;
  rejected: number;
}

export function MetricsGrid({ total, qualified, review, rejected }: MetricsGridProps): JSX.Element {
  return (
    <section className="metrics-grid" aria-label="Lead summary">
      <MetricCard label="Rows loaded" value={total} tone="blue" icon={FileSpreadsheet} />
      <MetricCard label="Qualified" value={qualified} tone="green" icon={CheckCircle2} />
      <MetricCard label="Needs review" value={review} tone="amber" icon={AlertTriangle} />
      <MetricCard label="Rejected" value={rejected} tone="red" icon={XCircle} />
    </section>
  );
}
