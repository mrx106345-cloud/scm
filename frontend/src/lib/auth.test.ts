import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { login, logout, me, getCsrfToken, apiRequest, shouldRedirectOn401 } from './auth';

const mockFetch = vi.fn() as ReturnType<typeof vi.fn> & typeof fetch;

beforeEach(() => {
  mockFetch.mockClear();
  vi.restoreAllMocks();
  // Reset CSRF token between tests
  (globalThis as { fetch?: typeof fetch }).fetch = mockFetch;
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('lib/auth', () => {
  describe('login', () => {
    it('posts credentials with credentials:include and CSRF header', async () => {
      mockFetch.mockResolvedValueOnce(new Response(null, { status: 204 }));
      // me() is called after login to return the user
      mockFetch.mockResolvedValueOnce(
        new Response(JSON.stringify({ id: 'u1', username: 'alice', role: 'admin' }), {
          status: 200,
        }),
      );

      const user = await login('alice', 'secret');

      expect(mockFetch).toHaveBeenCalledTimes(2);
      const [loginUrl, loginInit] = mockFetch.mock.calls[0];
      expect(loginUrl).toBe('/api/v1/auth/login');
      expect(loginInit.method).toBe('POST');
      expect(loginInit.credentials).toBe('include');
      expect(loginInit.headers).toMatchObject({
        'Content-Type': 'application/json',
        'X-CSRF-Token': expect.any(String),
      });
      expect(loginInit.body).toBe(JSON.stringify({ username: 'alice', password: 'secret' }));
      expect(user).toEqual({ id: 'u1', username: 'alice', role: 'admin' });
    });

    it('throws on 401 invalid credentials', async () => {
      mockFetch.mockResolvedValueOnce(new Response(null, { status: 401 }));

      await expect(login('alice', 'wrong')).rejects.toThrow('Invalid username or password');
    });

    it('throws on 403 account disabled', async () => {
      mockFetch.mockResolvedValueOnce(new Response(null, { status: 403 }));

      await expect(login('alice', 'secret')).rejects.toThrow('Account disabled');
    });

    it('rotates CSRF token after successful login', async () => {
      const tokenBefore = getCsrfToken();
      mockFetch.mockResolvedValueOnce(new Response(null, { status: 204 }));
      mockFetch.mockResolvedValueOnce(
        new Response(JSON.stringify({ id: 'u1', username: 'alice', role: 'viewer' }), {
          status: 200,
        }),
      );

      await login('alice', 'secret');

      expect(getCsrfToken()).not.toBe(tokenBefore);
    });
  });

  describe('logout', () => {
    it('posts to /auth/logout with CSRF header', async () => {
      mockFetch.mockResolvedValueOnce(new Response(null, { status: 204 }));

      await logout();

      expect(mockFetch).toHaveBeenCalledTimes(1);
      const [url, init] = mockFetch.mock.calls[0];
      expect(url).toBe('/api/v1/auth/logout');
      expect(init.method).toBe('POST');
      expect(init.credentials).toBe('include');
      expect(init.headers).toHaveProperty('X-CSRF-Token');
    });

    it('throws on non-ok response', async () => {
      mockFetch.mockResolvedValueOnce(new Response(null, { status: 500 }));

      await expect(logout()).rejects.toThrow('Logout failed');
    });

    it('rotates CSRF token after logout', async () => {
      const tokenBefore = getCsrfToken();
      mockFetch.mockResolvedValueOnce(new Response(null, { status: 204 }));

      await logout();

      expect(getCsrfToken()).not.toBe(tokenBefore);
    });
  });

  describe('me', () => {
    it('returns null on 401', async () => {
      mockFetch.mockResolvedValueOnce(new Response(null, { status: 401 }));

      const user = await me();
      expect(user).toBeNull();
    });

    it('returns user on 200', async () => {
      mockFetch.mockResolvedValueOnce(
        new Response(JSON.stringify({ id: 'u2', username: 'bob', role: 'planner' }), {
          status: 200,
        }),
      );

      const user = await me();
      expect(user).toEqual({ id: 'u2', username: 'bob', role: 'planner' });
    });

    it('throws on unexpected error', async () => {
      mockFetch.mockResolvedValueOnce(new Response(null, { status: 500 }));

      await expect(me()).rejects.toThrow('Auth check failed');
    });

    it('sends credentials:include', async () => {
      mockFetch.mockResolvedValueOnce(new Response(null, { status: 401 }));

      await me();

      const [, init] = mockFetch.mock.calls[0];
      expect(init.credentials).toBe('include');
      // GET requests should NOT have CSRF header
      expect(init.headers).not.toHaveProperty('X-CSRF-Token');
    });
  });

  describe('apiRequest (shared feature-data client)', () => {
    it('adds CSRF header + credentials on POST to a data endpoint', async () => {
      mockFetch.mockResolvedValueOnce(new Response(JSON.stringify({ ok: 1 }), { status: 200 }));

      const res = await apiRequest('/api/v1/chat/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: 'x' }),
      });
      expect(res.ok).toBe(true);
      const [url, init] = mockFetch.mock.calls[0];
      expect(url).toBe('/api/v1/chat/ask');
      expect(init.credentials).toBe('include');
      expect(init.headers).toHaveProperty('X-CSRF-Token');
    });

    it('passes non-auth 401 responses through without redirect loop on /login', async () => {
      mockFetch.mockResolvedValueOnce(new Response(null, { status: 401 }));
      window.history.pushState({}, '', '/login');

      const res = await apiRequest('/api/v1/dashboard/summary');
      expect(res.status).toBe(401);
    });

    it('enforces the same-origin path check', async () => {
      await expect(apiRequest('//evil.com/api')).rejects.toThrow('non same-origin');
    });
  });

  describe('shouldRedirectOn401 (routing decision)', () => {
    it('redirects on 401 from data endpoints', () => {
      expect(shouldRedirectOn401('/api/v1/dashboard/summary', '/')).toBe(true);
      expect(shouldRedirectOn401('/api/v1/chat/ask', '/suppliers')).toBe(true);
    });

    it('never redirects auth endpoints (normal logout/expiry signal)', () => {
      expect(shouldRedirectOn401('/auth/me', '/')).toBe(false);
      expect(shouldRedirectOn401('/auth/login', '/')).toBe(false);
      expect(shouldRedirectOn401('/auth/logout', '/')).toBe(false);
    });

    it('never redirects when already on /login (loop guard)', () => {
      expect(shouldRedirectOn401('/api/v1/dashboard/summary', '/login')).toBe(false);
    });
  });
});
