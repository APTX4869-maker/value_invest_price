import { InfoTip } from "./InfoTip";

export function GuidedMetric({ label, value, text, guide }) {
  return (
    <div className="guided-metric">
      <div>
        <strong>{label}{guide ? <InfoTip guide={guide} /> : null}</strong>
        <span>{text}</span>
      </div>
      <b>{value}</b>
    </div>
  );
}
