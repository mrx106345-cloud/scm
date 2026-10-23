import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AuthProvider, useAuth } from './useAuth';
import { login, logout, me } from '@/lib/auth';

vi.mock('@/lib/auth', () => ({
  login: vi.fn(),
  logout: vi.fn(),
  me: vi.fn(),
}));

const mockLogin = vi.mocked(login);
const mockLogout = vi.mocked(logout);
const mockMe = vi.mocked(me);

function Probe() {
  const { user, loading, isAuthenticated, login: doLogin, logout: doLogout } = useAuth();
  return (
    <div>
      {loading ? <span data-testid="loading">loading</span> : null}
      {user ? (
        <div data-testid="user">
          {user.username} ({user.role})
          <button data-testid="logout-btn" onClick={doLogout}>
            Sign out
          </button>
        </div>
      ) : (
        <div data-testid="not-authenticated">
          <input data-testid="username" />
          <input data-testid="password" />
          <button data-testid="login-btn" onClick={() => doLogin('alice', 'secret')}>
            Sign in
          </button>
        </div>
      )}
      {isAuthenticated ? <span data-testid="is-authenticated">yes</span> : null}
    </div>
  );
}

const mockUser = { id: 'u1', username: 'alice', role: 'admin' } as const;

describe('hooks/useAuth', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    mockLogin.mockReset();
    mockLogout.mockReset();
    mockMe.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('fetches current user on mount and shows authenticated UI', async () => {
    mockMe.mockResolvedValue(mockUser);

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    expect(screen.getByTestId('loading')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId('user')).toBeInTheDocument());
    expect(screen.getByTestId('user')).toHaveTextContent('alice (admin)');
    expect(screen.getByTestId('is-authenticated')).toBeInTheDocument();
    expect(mockMe).toHaveBeenCalledTimes(1);
  });

  it('shows not-authenticated UI when /auth/me returns 401', async () => {
    mockMe.mockResolvedValue(null);

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    await waitFor(() => expect(screen.getByTestId('not-authenticated')).toBeInTheDocument());
    expect(screen.queryByTestId('user')).not.toBeInTheDocument();
  });

  it('calls login on submit and refetches user', async () => {
    mockMe.mockResolvedValueOnce(null).mockResolvedValueOnce(mockUser);
    mockLogin.mockResolvedValue(mockUser);

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    await waitFor(() => expect(screen.getByTestId('not-authenticated')).toBeInTheDocument());

    const userInput = screen.getByTestId('username') as HTMLInputElement;
    const passInput = screen.getByTestId('password') as HTMLInputElement;
    await userEvent.type(userInput, 'alice');
    await userEvent.type(passInput, 'secret');
    await userEvent.click(screen.getByTestId('login-btn'));

    expect(mockLogin).toHaveBeenCalledWith('alice', 'secret');
    await waitFor(() => expect(screen.getByTestId('user')).toBeInTheDocument());
    expect(screen.getByTestId('user')).toHaveTextContent('alice (admin)');
  });

  it('calls logout and clears user', async () => {
    mockMe.mockResolvedValue(mockUser);
    mockLogout.mockResolvedValue(undefined);

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    await waitFor(() => expect(screen.getByTestId('user')).toBeInTheDocument());
    await userEvent.click(screen.getByTestId('logout-btn'));

    expect(mockLogout).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(screen.getByTestId('not-authenticated')).toBeInTheDocument());
  });
});
