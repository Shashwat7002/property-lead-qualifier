import { FileSpreadsheet, Hourglass, ShieldX, Star, Trophy } from "lucide-react";
import { MetricCard } from "./MetricCard";

interface MetricsGridProps {
  total: number;
  priorityA: number;
  priorityB: number;
  nurture: number;
  discard: number;
}

export function MetricsGrid({ total, priorityA, priorityB, nurture, discard }: MetricsGridProps): JSX.Element {
  return (
    <section className="metrics-grid" aria-label="Lead summary">
      <MetricCard label="Rows loaded" value={total} tone="blue" icon={FileSpreadsheet} />
      <MetricCard label="Priority A" value={priorityA} tone="green" icon={Trophy} />
      <MetricCard label="Priority B" value={priorityB} tone="teal" icon={Star} />
      <MetricCard label="Nurture C" value={nurture} tone="amber" icon={Hourglass} />
      <MetricCard label="Discard" value={discard} tone="red" icon={ShieldX} />
    </section>
  );
}
