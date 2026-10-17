import { type ReactNode, useEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';
import cn from '@/lib/cn';

export interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: ReactNode;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  showCloseButton?: boolean;
  footer?: ReactNode;
}

const sizeClasses = {
  sm: 'max-w-sm',
  md: 'max-w-md',
  lg: 'max-w-lg',
  xl: 'max-w-3xl',
};

export default function Modal({
  isOpen,
  onClose,
  title,
  description,
  children,
  size = 'md',
  showCloseButton = true,
  footer,
}: ModalProps) {
  const handleEscape = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    },
    [onClose],
  );

  useEffect(() => {
    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
      document.body.style.overflow = 'hidden';
    }
    return () => {
      document.removeEventListener('keydown', handleEscape);
      document.body.style.overflow = 'auto';
    };
  }, [isOpen, handleEscape]);

  if (!isOpen) return null;

  const content = (
    <div className="relative z-50" role="dialog" aria-modal="true" aria-label={title}>
      <div
        className="fixed inset-0 bg-black/40 backdrop-blur-sm"
        aria-hidden="true"
        onClick={onClose}
      />
      <div className="fixed inset-0 flex items-center justify-center p-4">
        <div
          className={cn(
            'w-full transform rounded-lg border border-border bg-background shadow-xl transition-all',
            sizeClasses[size],
          )}
        >
          <div className="flex items-start justify-between p-5 pb-0">
            <div>
              <h2 className="text-lg font-semibold text-foreground">{title}</h2>
              {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
            </div>
            {showCloseButton && (
              <button
                onClick={onClose}
                className="rounded-md p-1 hover:bg-accent text-muted-foreground hover:text-foreground transition-colors"
                aria-label="Close modal"
              >
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
          <div className="px-5 pt-4">{children}</div>
          {footer && <div className="flex justify-end gap-3 px-5 pb-5">{footer}</div>}
        </div>
      </div>
    </div>
  );

  return createPortal(content, document.body);
}
