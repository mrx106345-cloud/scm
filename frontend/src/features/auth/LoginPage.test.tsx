import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { LoginPage } from './LoginPage';
import { useAuth } from '@/hooks/useAuth';
import { login, type AuthUser } from '@/lib/auth';

function renderPage() {
  return render(
    <MemoryRouter>
      <LoginPage />
    </MemoryRouter>,
  );
}

vi.mock('@/hooks/useAuth', () => ({
  useAuth: vi.fn(),
}));
vi.mock('@/lib/auth', () => ({
  login: vi.fn(),
}));

const mockUseAuth = vi.mocked(useAuth);
const mockLogin = vi.mocked(login);

// Complete AuthContext stub with overridable fields; the page under test only
// consumes `login`. Cast through unknown because the real context's login is
// Promise<void> while lib/auth's login resolves a user (resolution value is
// ignored by the page).
type AuthCtx = ReturnType<typeof useAuth>;
const ctxStub = (overrides: Record<string, unknown> = {}): AuthCtx =>
  ({
    user: null,
    loading: false,
    isAuthenticated: false,
    logout: async () => {},
    refetch: async () => {},
    ...overrides,
  }) as unknown as AuthCtx;

describe('features/auth/LoginPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    mockUseAuth.mockReset();
    mockLogin.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders login form fields', () => {
    mockUseAuth.mockReturnValue(ctxStub({ login: mockLogin }));

    renderPage();

    expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
  });

  it('calls login with entered credentials on submit', async () => {
    mockUseAuth.mockReturnValue(ctxStub({ login: mockLogin }));
    mockLogin.mockResolvedValue({ id: 'u1', username: 'alice', role: 'viewer' } as const);

    renderPage();

    const userInput = screen.getByLabelText(/username/i) as HTMLInputElement;
    const passInput = screen.getByLabelText(/password/i) as HTMLInputElement;
    await userEvent.type(userInput, 'alice');
    await userEvent.type(passInput, 'secret');
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }));

    expect(mockLogin).toHaveBeenCalledWith('alice', 'secret');
  });

  it('shows error when login fails', async () => {
    mockUseAuth.mockReturnValue(ctxStub({ login: mockLogin }));
    mockLogin.mockRejectedValue(new Error('Invalid username or password'));

    renderPage();

    const userInput = screen.getByLabelText(/username/i) as HTMLInputElement;
    const passInput = screen.getByLabelText(/password/i) as HTMLInputElement;
    await userEvent.type(userInput, 'alice');
    await userEvent.type(passInput, 'wrong');
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() =>
      expect(screen.getByText('Invalid username or password')).toBeInTheDocument(),
    );
  });

  it('disables submit button while logging in', async () => {
    let resolveLogin!: (u: AuthUser) => void;
    mockUseAuth.mockReturnValue(ctxStub({ login: mockLogin }));
    mockLogin.mockImplementation(
      () => new Promise<AuthUser>((r) => (resolveLogin = r as (u: AuthUser) => void)),
    );

    renderPage();

    const userInput = screen.getByLabelText(/username/i) as HTMLInputElement;
    const passInput = screen.getByLabelText(/password/i) as HTMLInputElement;
    await userEvent.type(userInput, 'alice');
    await userEvent.type(passInput, 'secret');

    const btn = screen.getByRole('button', { name: /sign in/i });
    await userEvent.click(btn);
    expect(btn).toBeDisabled();

    resolveLogin({ id: 'u1', username: 'alice', role: 'viewer' });
    await waitFor(() => expect(btn).not.toBeDisabled());
  });
});
