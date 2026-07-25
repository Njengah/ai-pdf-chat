import { useEffect } from "react";

export type ToastMessage = {
  id: string;
  text: string;
  tone?: "ok" | "error";
};

type Props = {
  toasts: ToastMessage[];
  onDismiss: (id: string) => void;
};

export default function ToastStack({ toasts, onDismiss }: Props) {
  useEffect(() => {
    if (!toasts.length) return;
    const timers = toasts.map((toast) =>
      window.setTimeout(() => onDismiss(toast.id), 3200)
    );
    return () => timers.forEach((t) => window.clearTimeout(t));
  }, [toasts, onDismiss]);

  if (!toasts.length) return null;

  return (
    <div className="toast-stack" aria-live="polite">
      {toasts.map((toast) => (
        <div key={toast.id} className={`toast ${toast.tone || "ok"}`}>
          <span>{toast.text}</span>
          <button type="button" className="btn-icon" onClick={() => onDismiss(toast.id)}>
            ×
          </button>
        </div>
      ))}
    </div>
  );
}
