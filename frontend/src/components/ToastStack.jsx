import { AlertTriangle, CheckCircle2, Info, X } from "lucide-react";

const icons = {
  error: AlertTriangle,
  success: CheckCircle2,
  info: Info,
};

export function ToastStack({ toasts, dismissToast }) {
  if (!toasts.length) return null;

  return (
    <div className="toast-stack" role="status" aria-live="polite">
      {toasts.map((toast) => {
        const Icon = icons[toast.type] || Info;
        return (
          <div className={`toast ${toast.type || "info"}`} key={toast.id}>
            <Icon size={18} />
            <div>
              <strong>{toast.title}</strong>
              {toast.message ? <span>{toast.message}</span> : null}
            </div>
            <button type="button" aria-label="关闭提示" onClick={() => dismissToast(toast.id)}>
              <X size={16} />
            </button>
          </div>
        );
      })}
    </div>
  );
}
