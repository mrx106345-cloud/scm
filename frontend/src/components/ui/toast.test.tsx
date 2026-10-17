import { type ReactNode, useEffect } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ToastError, ToastProvider, ToastSuccess, useToast } from './toast';

function Trigger() {
  const { addToast } = useToast();
  return (
    <button
      onClick={() =>
        addToast({
          type: 'info',
          title: 'Heads up',
          description: 'Stock shifted',
          duration: 0,
          dismissible: true,
        })
      }
    >
      notify
    </button>
  );
}

function AddOnMount() {
  const { addToast } = useToast();
  useEffect(() => {
    addToast({ type: 'info', title: 'Sticky', duration: 0 });
  }, [addToast]);
  return null;
}

function renderProvider(ui: ReactNode) {
  return render(<ToastProvider>{ui}</ToastProvider>);
}

describe('useToast', () => {
  it('throws when used outside the provider', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    function Bare() {
      useToast();
      return null;
    }
    expect(() => render(<Bare />)).toThrow('useToast must be used within ToastProvider');
    spy.mockRestore();
  });
});

describe('ToastProvider', () => {
  it('adds a toast via the trigger button and renders it as an alert', async () => {
    const user = userEvent.setup();
    renderProvider(<Trigger />);
    await user.click(screen.getByRole('button', { name: 'notify' }));
    const alert = screen.getByRole('alert');
    expect(alert).toHaveTextContent('Heads up');
    expect(alert).toHaveTextContent('Stock shifted');
    expect(alert).toHaveClass('bg-info/10', 'border-info/20', 'text-info');
  });

  it('dismisses a dismissible toast through its button', async () => {
    const user = userEvent.setup();
    renderProvider(<Trigger />);
    await user.click(screen.getByRole('button', { name: 'notify' }));
    await user.click(screen.getByRole('button', { name: 'Dismiss notification' }));
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('keeps a toast with duration 0 until dismissed manually', () => {
    vi.useFakeTimers();
    try {
      renderProvider(<AddOnMount />);
      expect(screen.getByRole('alert')).toHaveTextContent('Sticky');
      act(() => {
        vi.advanceTimersByTime(10_000);
      });
      expect(screen.getByRole('alert')).toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });

  it('auto-dismisses after the default duration', () => {
    vi.useFakeTimers();
    try {
      renderProvider(<ToastSuccess title="Saved" duration={1000} />);
      expect(screen.getByRole('alert')).toHaveTextContent('Saved');
      act(() => {
        vi.advanceTimersByTime(1000);
      });
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });

  it('renders the error variant with error styling', () => {
    renderProvider(<ToastError title="Sync failed" description="Retry later" />);
    const alert = screen.getByRole('alert');
    expect(alert).toHaveTextContent('Sync failed');
    expect(alert).toHaveClass('bg-error/10', 'text-error');
  });

  it('omits the description paragraph when not provided', () => {
    renderProvider(<ToastSuccess title="Only title" />);
    const alert = screen.getByRole('alert');
    expect(alert).toHaveTextContent('Only title');
    expect(alert.querySelector('.text-muted-foreground')).toBeNull();
  });
});
