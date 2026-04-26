export function Stat({ label, value, hint, tone }) {
  return (
    <div className={`stat ${tone || ""}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      {hint ? <small>{hint}</small> : null}
    </div>
  );
}
