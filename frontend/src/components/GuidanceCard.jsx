import { CircleHelp } from "lucide-react";

export function GuidanceCard({ guide }) {
  return (
    <div className="guidance-card">
      <div className="guide-title">
        <CircleHelp size={16} />
        {guide.title}
      </div>
      <p>{guide.oneLine}</p>
      <p><strong>怎么看：</strong>{guide.standard}</p>
      <p><strong>对估值：</strong>{guide.impact}</p>
    </div>
  );
}
