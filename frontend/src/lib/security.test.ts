import { describe, expect, it } from 'vitest';
import { assertSameOriginApiPath, escapeHtml, isSameOriginApiPath } from './security';

describe('security helpers', () => {
  it('allows only same-origin api/auth paths', () => {
    expect(isSameOriginApiPath('/api/v1/items')).toBe(true);
    expect(isSameOriginApiPath('/api/v1/auth/login')).toBe(true);
    expect(isSameOriginApiPath('/auth/login')).toBe(true);
    expect(isSameOriginApiPath('/api')).toBe(true);
    expect(isSameOriginApiPath('/auth')).toBe(true);
  });

  it('rejects non same-origin or escaping paths', () => {
    // Protocol-relative URLs would leave the origin entirely.
    expect(isSameOriginApiPath('//evil.com/api')).toBe(false);
    expect(isSameOriginApiPath('https://example.com/api')).toBe(false);
    expect(isSameOriginApiPath('http://localhost/api/v1')).toBe(false);
    expect(isSameOriginApiPath('javascript:alert(1)')).toBe(false);
    // Bare paths outside the API namespace are not API endpoints.
    expect(isSameOriginApiPath('/foo/bar')).toBe(false);
    expect(isSameOriginApiPath('/apiv2/next')).toBe(false);
    expect(isSameOriginApiPath('/authorize-me')).toBe(false);
    expect(() => assertSameOriginApiPath('https://example.com/api')).toThrow();
    expect(() => assertSameOriginApiPath('//evil.com/api')).toThrow();
  });

  it('escapes html metacharacters', () => {
    expect(escapeHtml('<img src=x onerror="alert(1)">')).toContain('&' + 'lt;img');
  });
});
