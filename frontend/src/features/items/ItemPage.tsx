import { useQuery } from '@tanstack/react-query';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import Badge from '@/components/ui/badge';
import type { ItemDetail as ItemDetailType } from '@/types';

async function fetchItem(itemId: string): Promise<ItemDetailType> {
  const r = await fetch(`/api/v1/items/${encodeURIComponent(itemId)}`);
  if (!r.ok) throw new Error('Failed to fetch item');
  return r.json();
}

function StatusBadge({ status }: { status: string }) {
  const variant =
    status === 'in_stock'
      ? ('success' as const)
      : status === 'low_stock'
        ? ('warning' as const)
        : status === 'out_of_stock'
          ? ('error' as const)
          : ('secondary' as const);
  return (
    <Badge variant={variant} size="sm">
      {status.replace('_', ' ')}
    </Badge>
  );
}

export function ItemDetail({ itemId }: { itemId: string }) {
  const q = useQuery({
    queryKey: ['item', itemId],
    queryFn: () => fetchItem(itemId),
    enabled: !!itemId,
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
        <p className="text-sm text-error">Item unavailable. Please try again later.</p>
      </div>
    );
  }

  const i = q.data!;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">
          {i.sku} — {i.name}
        </h2>
        <StatusBadge status={i.status} />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Item Details</CardTitle>
          <CardDescription>Core inventory and pricing information</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-sm text-muted-foreground">Unit of Measure</p>
              <p className="font-medium">{i.uom}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Category</p>
              <p className="font-medium">{i.category ?? '—'}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Unit Cost</p>
              <p className="font-medium">{i.unit_cost ?? '—'}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">MOQ</p>
              <p className="font-medium">{i.moq}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Lot Multiple</p>
              <p className="font-medium">{i.lot_multiple}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Stockout Cost</p>
              <p className="font-medium">{i.stockout_cost ?? '—'}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {i.forecast && (
        <Card>
          <CardHeader>
            <CardTitle>Forecast</CardTitle>
            <CardDescription>Demand forecast for next period</CardDescription>
          </CardHeader>
          <CardContent>
            <pre className="text-xs bg-muted p-4 rounded-md overflow-x-auto">
              {JSON.stringify(i.forecast, null, 2)}
            </pre>
          </CardContent>
        </Card>
      )}

      {i.alert_history.length > 0 && (
        <Card>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left font-medium text-muted-foreground">Type</th>
                    <th className="text-left font-medium text-muted-foreground">Severity</th>
                    <th className="text-left font-medium text-muted-foreground">Status</th>
                    <th className="text-left font-medium text-muted-foreground">Score</th>
                    <th className="text-left font-medium text-muted-foreground">Expected Loss</th>
                    <th className="text-left font-medium text-muted-foreground">Created</th>
                  </tr>
                </thead>
                <tbody>
                  {i.alert_history.map((a) => (
                    <tr key={a.id} className="border-b border-border">
                      <td>{a.type}</td>
                      <td>{a.severity}</td>
                      <td>{a.status}</td>
                      <td>{a.score}</td>
                      <td>{a.expected_loss}</td>
                      <td>{a.created_at ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {i.open_pos.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Open POs</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left font-medium text-muted-foreground">PO</th>
                    <th className="text-left font-medium text-muted-foreground">Supplier</th>
                    <th className="text-left font-medium text-muted-foreground">Status</th>
                    <th className="text-left font-medium text-muted-foreground">Order Date</th>
                    <th className="text-left font-medium text-muted-foreground">Promised</th>
                    <th className="text-left font-medium text-muted-foreground">Qty</th>
                  </tr>
                </thead>
                <tbody>
                  {i.open_pos.map((p) => (
                    <tr key={p.po_id} className="border-b border-border">
                      <td>{p.po_number ?? '—'}</td>
                      <td>{p.supplier_id}</td>
                      <td>{p.status}</td>
                      <td>{p.order_date ?? '—'}</td>
                      <td>{p.promised_date ?? '—'}</td>
                      <td>{p.qty_ordered}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
