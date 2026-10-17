// Date formatting utility (dependency-free, uses Intl)
export default function formatDate(
  date: string | Date,
  options?: { relative?: boolean; locale?: string },
) {
  const d = new Date(date);
  if (options?.relative) {
    const diffMs = Date.now() - d.getTime();
    const mins = Math.round(diffMs / 60000);
    if (Math.abs(mins) < 1) return 'just now';
    if (Math.abs(mins) < 60) return `${Math.abs(mins)} min ago`;
    const hours = Math.round(mins / 60);
    if (Math.abs(hours) < 24) return `${Math.abs(hours)} h ago`;
    const days = Math.round(hours / 24);
    return `${Math.abs(days)} d ago`;
  }
  return new Intl.DateTimeFormat(options?.locale ?? 'en-IN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(d);
}

export function formatDateFull(date: string | Date) {
  return new Intl.DateTimeFormat('en-IN', { dateStyle: 'full', timeStyle: 'short' }).format(
    new Date(date),
  );
}

export function formatDateNoYear(date: string | Date) {
  return new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'long' }).format(new Date(date));
}
