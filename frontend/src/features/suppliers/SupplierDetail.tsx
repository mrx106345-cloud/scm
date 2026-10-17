import { useQuery } from '@tanstack/react-query';
import Badge from '@/components/ui/badge';
import type { SupplierDetail as SupplierDetailType } from '@/types';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

async function fetchSupplier(supplierId: string): Promise<SupplierDetailType> {
  const r = await fetch(`/api/v1/suppliers/${encodeURIComponent(supplierId)}`);
  if (!r.ok) throw new Error('Failed to fetch supplier');
  return r.json();
}

function StatusBadge({ active }: { active: boolean }) {
  return (
    <Badge variant={active ? 'success' : 'error'} size="sm">
      {active ? 'Active' : 'Inactive'}
    </Badge>
  );
}

export function SupplierDetail({ supplierId }: { supplierId: string }) {
  const q = useQuery({
    queryKey: ['supplier', supplierId],
    queryFn: () => fetchSupplier(supplierId),
    enabled: !!supplierId,
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
        <p className="text-sm text-error">Supplier unavailable. Please try again later.</p>
      </div>
    );
  }

  const s = q.data!;
  const rb = s.risk_breakdown;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">
          {s.code} — {s.name}
        </h2>
        <StatusBadge active={s.active} />
      </div>
      <p>Contract lead time: {s.contract_lead_time_days ?? '—'} days</p>

      {s.metrics && (
        <section>
          <h3 className="text-lg font-semibold">Metrics</h3>
          <table border={1} cellPadding="4">
            <tbody>
              <tr>
                <td>
                  <b>Mean lead time</b>
                </td>
                <td>
                  {s.metrics.mean_lt_recent != null
                    ? (s.metrics.mean_lt_recent as number).toFixed(1) + ' days'
                    : '—'}
                </td>
              </tr>
              <tr>
                <td>
                  <b>Drift %</b>
                </td>
                <td>
                  {s.metrics.drift_pct != null
                    ? ((s.metrics.drift_pct as number) * 100).toFixed(1) + '%'
                    : '—'}
                </td>
              </tr>
              <tr>
                <td>
                  <b>Dependency share</b>
                </td>
                <td>
                  {s.metrics.dependency_share != null
                    ? ((s.metrics.dependency_share as number) * 100).toFixed(0) + '%'
                    : '—'}
                </td>
              </tr>
              <tr>
                <td>
                  <b>Trend flag</b>
                </td>
                <td>{s.metrics.trend_flag ? 'Yes' : 'No'}</td>
              </tr>
            </tbody>
          </table>
        </section>
      )}

      {rb && (
        <section>
          <h3 className="text-lg font-semibold">Risk breakdown</h3>
          <table border={1} cellPadding="4">
            <tbody>
              <tr>
                <td>
                  <b>Drift component</b>
                </td>
                <td>{(rb.drift_component * 100).toFixed(1)}%</td>
              </tr>
              <tr>
                <td>
                  <b>On-time component</b>
                </td>
                <td>{(rb.on_time_component * 100).toFixed(1)}%</td>
              </tr>
              <tr>
                <td>
                  <b>Dependency component</b>
                </td>
                <td>{(rb.dependency_component * 100).toFixed(1)}%</td>
              </tr>
              <tr>
                <td>
                  <b>Total raw</b>
                </td>
                <td>{(rb.total_raw * 100).toFixed(1)}%</td>
              </tr>
            </tbody>
          </table>
        </section>
      )}

      {s.lead_time_trend.length > 0 && (
        <section>
          <h3 className="text-lg font-semibold">Lead-time trend</h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={s.lead_time_trend}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="receipt_date" />
              <YAxis />
              <Tooltip />
              <Line type="monotone" dataKey="lead_days" stroke="#8884d8" strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </section>
      )}

      {s.items_exposed.length > 0 && (
        <section>
          <h3 className="text-lg font-semibold">Items exposed (open POs)</h3>
          <table border={1} cellPadding="4">
            <thead>
              <tr>
                <th>SKU</th>
                <th>Name</th>
                <th>Criticality</th>
                <th>PO</th>
                <th>Status</th>
                <th>Qty</th>
              </tr>
            </thead>
            <tbody>
              {s.items_exposed.map((e) => (
                <tr key={e.item_id}>
                  <td>{e.sku}</td>
                  <td>{e.name}</td>
                  <td>{e.criticality}</td>
                  <td>{e.po_number ?? '—'}</td>
                  <td>{e.po_status ?? '—'}</td>
                  <td>{e.qty_ordered}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
}
