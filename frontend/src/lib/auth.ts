// Auth API client for SCM Agent frontend.
// Talks to the backend /auth endpoints (PART L) over same-origin /api.
// Session is an HTTP-only cookie; the browser sends it automatically with
// credentials: 'include'. A CSRF token header is added to every non-GET
// request (the backend checks presence, not cryptographic validity).
import { assertSameOriginApiPath } from './security';

const API_PREFIX = '/api';

// One CSRF token per page load. Regenerated on logout/login boundaries.
let csrfToken = crypto.randomUUID();

function rotateCsrfToken(): void {
  csrfToken = crypto.randomUUID();
}

export function getCsrfToken(): string {
  return csrfToken;
}

function copyHeaders(headers?: HeadersInit): Record<string, string> {
  if (!headers) return {};
  if (headers instanceof Headers) {
    const out: Record<string, string> = {};
    headers.forEach((value, key) => {
      out[key] = value;
    });
    return out;
  }
  if (Array.isArray(headers)) {
    return Object.fromEntries(headers);
  }
  return { ...headers };
}

async function request(path: string, init: RequestInit = {}): Promise<Response> {
  assertSameOriginApiPath(path);

  const headers: Record<string, string> = copyHeaders(init.headers);

  const method = (init.method ?? 'GET').toUpperCase();
  if (method !== 'GET' && method !== 'HEAD' && method !== 'OPTIONS') {
    headers['X-CSRF-Token'] = getCsrfToken();
  }

  const res = await fetch(`${API_PREFIX}${path}`, {
    ...init,
    credentials: 'include',
    headers,
  });
  return res;
}

export type AuthUser = {
  id: string;
  username: string;
  role: 'admin' | 'planner' | 'purchaser' | 'viewer';
};

export async function login(username: string, password: string): Promise<AuthUser> {
  const res = await request('/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    // 401 invalid credentials; 403 account disabled; 429 locked out.
    throw new Error(res.status === 403 ? 'Account disabled' : 'Invalid username or password');
  }
  rotateCsrfToken();
  const user = await me();
  if (!user) {
    throw new Error('Login succeeded but no user returned');
  }
  return user;
}

export async function logout(): Promise<void> {
  const res = await request('/auth/logout', { method: 'POST' });
  if (!res.ok) {
    throw new Error('Logout failed');
  }
  rotateCsrfToken();
}

export async function me(): Promise<AuthUser | null> {
  const res = await request('/auth/me');
  if (res.status === 401) {
    return null;
  }
  if (!res.ok) {
    throw new Error('Auth check failed');
  }
  return (await res.json()) as AuthUser;
}
