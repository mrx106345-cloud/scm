import { describe, expect, it } from 'vitest';
import { assertSameOriginApiPath, escapeHtml, isSameOriginApiPath } from './security';

describe('security helpers', () => {
  it('allows only same-origin /api paths', () => {
    expect(isSameOriginApiPath('/api/v1/items')).toBe(true);
    expect(isSameOriginApiPath('https://example.com/api')).toBe(false);
    expect(() => assertSameOriginApiPath('https://example.com/api')).toThrow();
  });

  it('escapes html metacharacters', () => {
    expect(escapeHtml('<img src=x onerror="alert(1)">')).toContain('&lt;img');
  });
});
