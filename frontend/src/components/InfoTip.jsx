import { CircleHelp } from "lucide-react";

export function InfoTip({ guide }) {
  return (
    <span className="info-tip">
      <CircleHelp size={15} />
      <span className="tip-popover">
        <strong>{guide.title}</strong>
        <span>{guide.oneLine}</span>
        <span><b>怎么看：</b>{guide.standard}</span>
        <span><b>对估值：</b>{guide.impact}</span>
      </span>
    </span>
  );
}
