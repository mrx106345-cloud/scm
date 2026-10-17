import { type ReactNode } from 'react';
import cn from '@/lib/cn';

export interface TableColumn<T extends Record<string, unknown>> {
  header: string;
  accessor: keyof T;
  width?: string;
  className?: string;
  render?: (cell: unknown, row: T) => ReactNode;
}

export interface TableProps<T extends Record<string, unknown>> {
  columns: TableColumn<T>[];
  data: T[];
  className?: string;
}

export default function Table<T extends Record<string, unknown>>({
  columns,
  data,
  className,
}: TableProps<T>) {
  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center py-8">
        <p className="text-sm text-muted-foreground">No data available</p>
      </div>
    );
  }

  return (
    <div className={cn('min-w-full', className)}>
      <table className="w-full caption-bottom text-sm">
        <thead>
          <tr className="border-b border-border">
            {columns.map((col) => (
              <th
                key={String(col.accessor)}
                className="h-10 px-3 text-left font-medium text-muted-foreground uppercase tracking-wider"
                style={col.width ? { width: col.width } : undefined}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {data.map((row, rowIndex) => (
            <tr
              key={String((row[Object.keys(row)[0] as keyof T] as unknown) ?? rowIndex)}
              className={cn(
                'transition-colors hover:bg-accent/50',
                rowIndex % 2 === 1 && 'bg-muted/30',
              )}
            >
              {columns.map((col) => {
                const value = row[col.accessor];
                return (
                  <td
                    key={String(col.accessor)}
                    className={cn('px-3 py-2 text-foreground', col.className)}
                  >
                    {col.render ? col.render(value as never, row) : String(value ?? '—')}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
