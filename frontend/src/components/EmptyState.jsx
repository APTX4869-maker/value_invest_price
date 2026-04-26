import { ShieldCheck } from "lucide-react";

export function EmptyState({ title, text }) {
  return (
    <div className="empty-state">
      <ShieldCheck size={28} />
      <h3>{title}</h3>
      <p>{text}</p>
    </div>
  );
}
