import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import Textarea from './textarea';

describe('Textarea', () => {
  it('associates the label with the textarea (derived id)', () => {
    render(<SupplierNote />);
    const area = screen.getByLabelText('Supplier Note');
    expect(area).toHaveAttribute('id', 'supplier-note');
    expect(area.tagName).toBe('TEXTAREA');
  });

  it('accepts typed text and fires onChange', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Textarea label="Comment" onChange={onChange} />);
    const area = screen.getByLabelText('Comment');
    await user.type(area, 'hi');
    expect(area).toHaveValue('hi');
    expect(onChange).toHaveBeenCalledTimes(2);
  });

  it('announces an error with aria attributes and message', () => {
    render(<Textarea label="Reason" error="Cannot be empty" />);
    const area = screen.getByLabelText('Reason');
    expect(screen.getByText('Cannot be empty')).toHaveAttribute('id', 'reason-error');
    expect(area).toHaveAttribute('aria-invalid', 'true');
    expect(area).toHaveAttribute('aria-describedby', 'reason-error');
  });

  it('shows placeholder text', () => {
    render(<Textarea label="Notes" placeholder="Delay reason…" />);
    expect(screen.getByPlaceholderText('Delay reason…')).toBeInTheDocument();
  });
});

function SupplierNote() {
  return <Textarea label="Supplier Note" />;
}
