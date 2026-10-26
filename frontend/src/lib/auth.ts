// Auth API client for SCM Agent frontend.
// Talks to the backend /api/v1/auth endpoints over same-origin paths (the
// api-spec A0 base path is /api/v1; PART L routes live under it). The session
// is an HTTP-only cookie; the browser sends it automatically with
// credentials: 'include'. A CSRF token header is added to every non-GET
// request (the backend checks presence, not cryptographic validity).
import { assertSameOriginApiPath } from './security';

const API_PREFIX = '/api/v1';

// One CSRF token per page load. Regenerated on logout/login boundaries.
let csrfToken = crypto.randomUUID();

function rotateCsrfToken(): void {
  csrfToken = crypto.randomUUID();
}

export function getCsrfToken(): string {
  return csrfToken;
}

// Auth endpoints manage the session itself; a 401 there is a normal signal,
// not a reason to bounce the user to /login (avoids redirect loops).
const AUTH_PATH = /\/auth\//;

/**
 * Decide whether a 401 response should send the user to /login.
 * Pure so the routing decision is unit-testable without real navigation.
 */
export function shouldRedirectOn401(path: string, pathname: string): boolean {
  return !AUTH_PATH.test(path) && !pathname.startsWith('/login');
}

/**
 * Shared same-origin request client for feature data (dashboard, alerts,
 * chat, ...). Same-origin path enforcement, CSRF header on non-GET,
 * cookie credentials, and a global 401 handler that returns the user to
 * the login screen once (other than on auth endpoints).
 */
export async function apiRequest(path: string, init: RequestInit = {}): Promise<Response> {
  assertSameOriginApiPath(path);
  const res = await net(path, init);
  if (res.status === 401 && shouldRedirectOn401(path, window.location.pathname)) {
    // Session expired mid-use: send the user back to the login screen.
    window.location.assign('/login');
  }
  return res;
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

async function net(path: string, init: RequestInit): Promise<Response> {
  const headers: Record<string, string> = copyHeaders(init.headers);

  const method = (init.method ?? 'GET').toUpperCase();
  if (method !== 'GET' && method !== 'HEAD' && method !== 'OPTIONS') {
    headers['X-CSRF-Token'] = getCsrfToken();
  }

  return fetch(path, {
    ...init,
    credentials: 'include',
    headers,
  });
}

// Internal: auth endpoints are paths relative to the API prefix.
async function request(path: string, init: RequestInit = {}): Promise<Response> {
  assertSameOriginApiPath(path);
  return net(`${API_PREFIX}${path}`, init);
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
