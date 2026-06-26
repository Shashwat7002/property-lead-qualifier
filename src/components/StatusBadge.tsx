import { AlertTriangle, CheckCircle2, XCircle } from "lucide-react";
import { QualificationStatus } from "../types";

const statusLabels: Record<QualificationStatus, string> = {
  qualified: "Qualified",
  review: "Needs review",
  rejected: "Rejected",
};

interface StatusBadgeProps {
  status: QualificationStatus;
}

export function StatusBadge({ status }: StatusBadgeProps): JSX.Element {
  const Icon = status === "qualified" ? CheckCircle2 : status === "review" ? AlertTriangle : XCircle;

  return (
    <span className={`status-badge status-${status}`}>
      <Icon aria-hidden="true" size={15} />
      {statusLabels[status]}
    </span>
  );
}
