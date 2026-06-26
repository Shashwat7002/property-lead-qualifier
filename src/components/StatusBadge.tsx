import { AlertTriangle, ShieldX, Star, Trophy } from "lucide-react";
import { QualificationStatus } from "../types";

const statusLabels: Record<QualificationStatus, string> = {
  "priority-a": "Priority A",
  "priority-b": "Priority B",
  nurture: "Nurture C",
  discard: "Discard",
};

interface StatusBadgeProps {
  status: QualificationStatus;
}

export function StatusBadge({ status }: StatusBadgeProps): JSX.Element {
  const Icon =
    status === "priority-a" ? Trophy : status === "priority-b" ? Star : status === "nurture" ? AlertTriangle : ShieldX;

  return (
    <span className={`status-badge status-${status}`}>
      <Icon aria-hidden="true" size={15} />
      {statusLabels[status]}
    </span>
  );
}
