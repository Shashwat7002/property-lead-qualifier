import { LucideIcon } from "lucide-react";

interface MetricCardProps {
  label: string;
  value: string | number;
  tone: "green" | "amber" | "red" | "blue" | "teal";
  icon: LucideIcon;
}

export function MetricCard({ label, value, tone, icon: Icon }: MetricCardProps): JSX.Element {
  return (
    <div className={`metric-card metric-card-${tone}`}>
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
      </div>
      <Icon aria-hidden="true" size={22} />
    </div>
  );
}
