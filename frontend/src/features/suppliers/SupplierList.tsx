import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import Badge from '@/components/ui/badge';
import type { SupplierRow } from '@/types';

async function fetchSuppliers(): Promise<{
  items: SupplierRow[];
  page: number;
  pageSize: number;
  total: number;
}> {
  const r = await fetch('/api/v1/suppliers');
  if (!r.ok) throw new Error('Failed to fetch suppliers');
  return r.json();
}

function StatusBadge({ active }: { active: boolean }) {
  return (
    <Badge variant={active ? 'success' : 'error'} size="sm">
      {active ? 'Active' : 'Inactive'}
    </Badge>
  );
}

function TrendBadge({ trendFlag }: { trendFlag: boolean | null }) {
  return (
    <Badge variant={trendFlag ? 'warning' : 'secondary'} size="sm">
      {trendFlag ? 'Up' : 'Stable'}
    </Badge>
  );
}

function formatPercentage(value: number | null) {
  if (value == null) return '—';
  return (value * 100).toFixed(0) + '%';
}

function formatDays(value: number | null) {
  if (value == null) return '—';
  return value.toFixed(1) + ' days';
}

export function SupplierList() {
  const q = useQuery({
    queryKey: ['suppliers'],
    queryFn: fetchSuppliers,
  });

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
        <p className="text-sm text-error">Suppliers unavailable. Please try again later.</p>
      </div>
    );
  }

  const { items = [], total } = q.data!;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">Suppliers</h2>
        <Link to="/suppliers" className="text-sm text-primary hover:underline">
          View all ({total})
        </Link>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Supplier Performance</CardTitle>
          <CardDescription>Risk scores and on-time delivery metrics</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left font-medium text-muted-foreground">Code</th>
                  <th className="text-left font-medium text-muted-foreground">Name</th>
                  <th className="text-left font-medium text-muted-foreground">Risk Score</th>
                  <th className="text-left font-medium text-muted-foreground">On-Time Rate</th>
                  <th className="text-left font-medium text-muted-foreground">Mean Lead Time</th>
                  <th className="text-left font-medium text-muted-foreground">Trend</th>
                  <th className="text-left font-medium text-muted-foreground">Status</th>
                </tr>
              </thead>
              <tbody>
                {items.map((s) => (
                  <tr key={s.id} className="border-b border-border">
                    <td className="font-mono">
                      <Link to={`/suppliers/${s.id}`} className="text-primary hover:underline">
                        {s.code}
                      </Link>
                    </td>
                    <td className="font-medium">{s.name}</td>
                    <td>{s.risk_score != null ? s.risk_score.toFixed(1) : '—'}</td>
                    <td>{formatPercentage(s.on_time_rate)}</td>
                    <td>{formatDays(s.mean_lt_recent)}</td>
                    <td>
                      <TrendBadge trendFlag={s.trend_flag} />
                    </td>
                    <td>
                      <StatusBadge active={s.active} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
