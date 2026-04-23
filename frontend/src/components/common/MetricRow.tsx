type MetricRowProps = {
  label: string;
  value: string;
};

export function MetricRow({ label, value }: MetricRowProps) {
  return (
    <div>
      <span>{label}</span>
      <b>{value}</b>
    </div>
  );
}
