import { Component, type ReactNode } from 'react';

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  message: string;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false, message: '' };

  static getDerivedStateFromError(error: unknown): ErrorBoundaryState {
    return {
      hasError: true,
      message: error instanceof Error ? error.message : 'Something went wrong.',
    };
  }

  render() {
    if (this.state.hasError) {
      return (
        this.props.fallback ?? (
          <div
            role="alert"
            className="flex min-h-[40vh] flex-col items-center justify-center gap-2 p-8 text-center"
          >
            <h1 className="text-lg font-semibold">Something went wrong</h1>
            <p className="max-w-md text-sm text-muted-foreground">
              The page hit an unexpected error. Reload to try again. Technical detail:{' '}
              {this.state.message}
            </p>
            <button
              type="button"
              className="rounded-md border border-input px-4 py-2 text-sm"
              onClick={() => window.location.reload()}
            >
              Reload page
            </button>
          </div>
        )
      );
    }
    return this.props.children;
  }
}
