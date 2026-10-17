import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import Table, { type TableColumn } from './table';

interface Row extends Record<string, unknown> {
  id: number;
  name: string;
  qty: number | null;
}

const columns: TableColumn<Row>[] = [
  { header: 'ID', accessor: 'id', width: '80px' },
  { header: 'Name', accessor: 'name' },
  { header: 'Qty', accessor: 'qty' },
];

const data: Row[] = [
  { id: 1, name: 'Bolt M8', qty: 120 },
  { id: 2, name: 'Nut M8', qty: null },
];

describe('Table', () => {
  it('shows an empty state instead of a table', () => {
    render(<Table columns={columns} data={[]} />);
    expect(screen.getByText('No data available')).toBeInTheDocument();
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
  });

  it('renders headers and rows', () => {
    render(<Table columns={columns} data={data} />);
    expect(screen.getByRole('table')).toBeInTheDocument();
    const headers = screen.getAllByRole('columnheader');
    expect(headers.map((h) => h.textContent)).toEqual(['ID', 'Name', 'Qty']);
    expect(screen.getAllByRole('row')).toHaveLength(1 + data.length);
    expect(screen.getByText('Bolt M8')).toBeInTheDocument();
    expect(screen.getByText('Nut M8')).toBeInTheDocument();
  });

  it('applies the column width to the header cell', () => {
    render(<Table columns={columns} data={data} />);
    expect(screen.getAllByRole('columnheader')[0]).toHaveStyle({ width: '80px' });
  });

  it('renders nullish values as an em dash', () => {
    render(<Table columns={columns} data={data} />);
    expect(screen.getByText('—')).toBeInTheDocument();
  });

  it('uses a custom render function when provided', () => {
    const cols: TableColumn<Row>[] = [
      ...columns.slice(0, 2),
      { ...columns[2], render: (value) => `${value ?? 0} units` },
    ];
    render(<Table columns={cols} data={data} />);
    expect(screen.getByText('120 units')).toBeInTheDocument();
    expect(screen.getByText('0 units')).toBeInTheDocument();
  });

  it('merges a custom className onto the wrapper', () => {
    const { container } = render(<Table columns={columns} data={data} className="my-table" />);
    expect(container.firstElementChild).toHaveClass('min-w-full', 'my-table');
  });
});
