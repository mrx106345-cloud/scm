// Security helpers shared by the frontend.
//
// The SCM Agent must stay fully offline and must never execute instructions
// found in ERP/chat payloads. These helpers sanitize strings before they are
// rendered and keep API URLs pinned to same-origin paths (blocking http://,
// https://, and javascript: URLs).

const SAME_ORIGIN_API = /^\//;

export function isSameOriginApiPath(path: string): boolean {
  return SAME_ORIGIN_API.test(path);
}

export function assertSameOriginApiPath(path: string): string {
  if (!isSameOriginApiPath(path)) {
    throw new Error('Blocked non same-origin API path: ' + path);
  }
  return path;
}

/** Escape text before it is interpolated into HTML or SVG contexts. */
export function escapeHtml(input: string): string {
  return input
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}
