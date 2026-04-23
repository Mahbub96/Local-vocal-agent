import { getStatusLabel } from "../../utils/thinkingStatus";

type StatusBadgeProps = {
  status: string;
};

export function StatusBadge({ status }: StatusBadgeProps) {
  const label = getStatusLabel(status);
  return <em className={label}>{label}</em>;
}
