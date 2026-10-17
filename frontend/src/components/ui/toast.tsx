import {
  type ReactNode,
  createContext,
  useCallback,
  useContext,
  useState,
  useRef,
  useEffect,
} from 'react';
import cn from '@/lib/cn';

export type ToastType = 'success' | 'error' | 'warning' | 'info';

export interface ToastItem {
  id: string;
  type: ToastType;
  title: string;
  description?: string;
  duration?: number;
  dismissible?: boolean;
}

interface ToastContextValue {
  toasts: ToastItem[];
  addToast: (toast: Omit<ToastItem, 'id'>) => void;
  removeToast: (id: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within ToastProvider');
  }
  return context;
}

const typeStyles = {
  success: 'bg-success/10 border-success/20 text-success',
  error: 'bg-error/10 border-error/20 text-error',
  warning: 'bg-warning/10 border-warning/20 text-warning',
  info: 'bg-info/10 border-info/20 text-info',
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const idRef = useRef(0);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const addToast = useCallback(
    (toast: Omit<ToastItem, 'id'>) => {
      const id = `toast-${idRef.current++}`;
      const newToast = { ...toast, id };
      setToasts((prev) => [...prev, newToast]);

      if (toast.duration !== 0) {
        setTimeout(() => {
          removeToast(id);
        }, toast.duration ?? 5000);
      }
    },
    [removeToast],
  );

  return (
    <ToastContext.Provider value={{ toasts, addToast, removeToast }}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex w-full max-w-sm flex-col gap-2 px-4">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={cn(
              'flex items-start gap-3 rounded-lg border bg-background p-3 shadow-lg animate-[slideIn_0.2s_ease-out]',
              typeStyles[toast.type],
            )}
            role="alert"
          >
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold">{toast.title}</p>
              {toast.description && (
                <p className="mt-0.5 text-xs text-muted-foreground">{toast.description}</p>
              )}
            </div>
            {toast.dismissible && (
              <button
                className="text-muted-foreground hover:text-foreground transition-colors"
                onClick={() => removeToast(toast.id)}
                aria-label="Dismiss notification"
              >
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </button>
            )}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function ToastSuccess({
  title,
  description,
  duration = 5000,
}: {
  title: string;
  description?: string;
  duration?: number;
}) {
  const { addToast } = useToast();
  useEffect(() => {
    addToast({
      type: 'success',
      title,
      ...(description === undefined ? {} : { description }),
      duration,
    });
  }, [title, description, duration, addToast]);
  return null;
}

export function ToastError({
  title,
  description,
  duration = 5000,
}: {
  title: string;
  description?: string;
  duration?: number;
}) {
  const { addToast } = useToast();
  useEffect(() => {
    addToast({
      type: 'error',
      title,
      ...(description === undefined ? {} : { description }),
      duration,
    });
  }, [title, description, duration, addToast]);
  return null;
}

export function ToastInfo({
  title,
  description,
  duration = 5000,
}: {
  title: string;
  description?: string;
  duration?: number;
}) {
  const { addToast } = useToast();
  useEffect(() => {
    addToast({
      type: 'info',
      title,
      ...(description === undefined ? {} : { description }),
      duration,
    });
  }, [title, description, duration, addToast]);
  return null;
}
