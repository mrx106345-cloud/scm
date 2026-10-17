import { useQuery } from '@tanstack/react-query';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import Badge from '@/components/ui/badge';
import formatDate from '@/lib/format-date';
import formatCurrency from '@/lib/format-currency';

type Summary = {
  as_of: string;
  alerts: { critical: number; high: number; medium: number };
  expected_loss_at_risk: { amount: string; label: string };
  data_quality: { score: number };
  pending_recommendations: number;
};

async function fetchSummary(): Promise<Summary> {
  const r = await fetch('/api/v1/dashboard/summary');
  if (!r.ok) throw new Error('Failed to fetch dashboard summary');
  return r.json();
}

export function Dashboard() {
  const q = useQuery({ queryKey: ['summary'], queryFn: fetchSummary });

  if (q.isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  if (q.error) {
    return (
      <div className="flex items-center justify-center py-8">
        <p className="text-sm text-error">Dashboard unavailable. Please try again later.</p>
      </div>
    );
  }

  const s = q.data!;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight">SCM Agent — Dashboard</h1>
        <Badge variant="info">Live</Badge>
      </div>
      <p className="text-sm text-muted-foreground">
        Data as of {formatDate(s.as_of, { relative: true })}
      </p>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0">
            <CardTitle className="text-sm font-medium">Critical Alerts</CardTitle>
            <svg
              className="h-4 w-4 text-error"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4.5c-.77-.833-2.694-.833-3.464 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z"
              />
            </svg>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{s.alerts.critical}</div>
            <p className="text-xs text-muted-foreground">Critical severity alerts</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0">
            <CardTitle className="text-sm font-medium">High Severity</CardTitle>
            <svg
              className="h-4 w-4 text-warning"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4.5c-.77-.833-2.694-.833-3.464 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z"
              />
            </svg>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{s.alerts.high}</div>
            <p className="text-xs text-muted-foreground">High severity alerts</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0">
            <CardTitle className="text-sm font-medium">Pending Recommendations</CardTitle>
            <svg
              className="h-4 w-4 text-info"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 6v6m0 0v6m0-6h6m-6 0H6"
              />
            </svg>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{s.pending_recommendations}</div>
            <p className="text-xs text-muted-foreground">Awaiting approval</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0">
            <CardTitle className="text-sm font-medium">Data Quality</CardTitle>
            <svg
              className="h-4 w-4 text-secondary"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
              />
            </svg>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{s.data_quality.score}/100</div>
            <p className="text-xs text-muted-foreground">Data quality score</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Risk Overview</CardTitle>
          <CardDescription>Expected loss at risk this period</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-3xl font-bold">{formatCurrency(s.expected_loss_at_risk.amount)}</div>
          <p className="text-sm text-muted-foreground">{s.expected_loss_at_risk.label}</p>
        </CardContent>
      </Card>
    </div>
  );
}
