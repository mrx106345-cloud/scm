import { describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom';
import { ProtectedRoute } from './ProtectedRoute';
import { AuthProvider } from '@/hooks/useAuth';
import { me } from '@/lib/auth';

vi.mock('@/lib/auth', () => ({
  login: vi.fn(),
  logout: vi.fn(),
  me: vi.fn(),
}));

const mockMe = vi.mocked(me);

function LoginPageProbe() {
  const location = useLocation();
  return (
    <div>
      <span data-testid="login-page">login-page</span>
      <span data-testid="login-state">{JSON.stringify(location.state)}</span>
    </div>
  );
}

function Child() {
  return <div data-testid="protected-content">secret</div>;
}

describe('components/layout/ProtectedRoute', () => {
  it('redirects unauthenticated users to /login preserving the origin path', async () => {
    mockMe.mockResolvedValue(null);

    render(
      <MemoryRouter initialEntries={['/suppliers']}>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<LoginPageProbe />} />
            <Route
              path="/suppliers"
              element={
                <ProtectedRoute>
                  <Child />
                </ProtectedRoute>
              }
            />
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByTestId('login-page')).toBeInTheDocument());
    expect(screen.queryByTestId('protected-content')).toBeNull();
    // The original location rides along in state so login can return the user.
    expect(screen.getByTestId('login-state').textContent).toContain('suppliers');
  });

  it('renders the protected children when authenticated', async () => {
    mockMe.mockResolvedValue({ id: 'u1', username: 'alice', role: 'planner' });

    render(
      <MemoryRouter initialEntries={['/']}>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<LoginPageProbe />} />
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <Child />
                </ProtectedRoute>
              }
            />
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByTestId('protected-content')).toBeInTheDocument());
    expect(screen.getByTestId('protected-content')).toHaveTextContent('secret');
    expect(screen.queryByTestId('login-page')).toBeNull();
  });

  it('shows the signing-in placeholder while the session check is in flight', async () => {
    vi.useFakeTimers();
    try {
      mockMe.mockReturnValue(
        new Promise(() => {
          /* never resolves: session check pending */
        }) as unknown as Promise<{ id: string; username: string; role: 'viewer' }>,
      );

      render(
        <MemoryRouter initialEntries={['/']}>
          <AuthProvider>
            <ProtectedRoute>
              <Child />
            </ProtectedRoute>
          </AuthProvider>
        </MemoryRouter>,
      );

      expect(screen.getByText('Signing in…')).toBeInTheDocument();
      expect(screen.queryByTestId('protected-content')).toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });

  it('uses the auth context (throws outside AuthProvider)', () => {
    // useAuth throws when rendered without a provider — guards against
    // ProtectedRoute silently bypassing authentication.
    expect(() =>
      render(
        <MemoryRouter>
          <ProtectedRoute>
            <Child />
          </ProtectedRoute>
        </MemoryRouter>,
      ),
    ).toThrow('useAuth must be used within an AuthProvider');
  });
});
