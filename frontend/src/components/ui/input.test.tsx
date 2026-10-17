import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import Input from './input';

describe('Input', () => {
  it('associates the label with the input (derived id)', () => {
    render(<Input label="Reorder Point" />);
    const input = screen.getByLabelText<HTMLInputElement>('Reorder Point');
    expect(input).toHaveAttribute('id', 'reorder-point');
    expect(input.type).toBe('text');
  });

  it('prefers an explicit id over the derived one', () => {
    render(<Input label="SKU" id="custom-id" />);
    expect(screen.getByLabelText('SKU')).toHaveAttribute('id', 'custom-id');
  });

  it('accepts typed values', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Input label="Search" onChange={onChange} />);
    const input = screen.getByLabelText('Search');
    await user.type(input, 'bolt');
    expect(input).toHaveValue('bolt');
    expect(onChange).toHaveBeenCalledTimes(4);
  });

  it('announces an error with aria attributes and message', () => {
    render(<Input label="Email" error="Required field" />);
    const input = screen.getByLabelText('Email');
    expect(screen.getByText('Required field')).toBeInTheDocument();
    expect(input).toHaveAttribute('aria-invalid', 'true');
    expect(input).toHaveAttribute('aria-describedby', 'email-error');
    expect(screen.getByText('Required field')).toHaveAttribute('id', 'email-error');
  });

  it('hides the visual message when showError is false but keeps invalid state', () => {
    render(<Input label="Email" error="Too late" showError={false} />);
    const input = screen.getByLabelText('Email');
    expect(screen.queryByText('Too late')).not.toBeInTheDocument();
    expect(input).toHaveAttribute('aria-invalid', 'true');
    expect(input).not.toHaveAttribute('aria-describedby');
  });

  it('is not invalid without an error', () => {
    render(<Input label="Qty" />);
    expect(screen.getByLabelText('Qty')).toHaveAttribute('aria-invalid', 'false');
    expect(screen.getByLabelText('Qty')).not.toHaveAttribute('aria-describedby');
  });

  it('forwards disabled state', () => {
    render(<Input label="Locked" disabled />);
    expect(screen.getByLabelText('Locked')).toBeDisabled();
  });
});
