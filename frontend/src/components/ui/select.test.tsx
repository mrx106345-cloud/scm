import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import Select from './select';

const options = [
  { value: 'high', label: 'High' },
  { value: 'low', label: 'Low' },
];

describe('Select', () => {
  it('renders every option with its label', () => {
    render(<Select label="Priority" options={options} />);
    expect(screen.getByRole('option', { name: 'High' })).toHaveAttribute('value', 'high');
    expect(screen.getByRole('option', { name: 'Low' })).toHaveAttribute('value', 'low');
  });

  it('renders a disabled placeholder as the first option', () => {
    render(<Select label="Priority" options={options} placeholder="Choose…" />);
    const placeholder = screen.getByRole('option', { name: 'Choose…' });
    expect(placeholder).toBeDisabled();
    expect(placeholder).toHaveAttribute('value', '');
    expect(screen.getByLabelText('Priority')).toHaveValue('');
  });

  it('associates the label with the select (derived id)', () => {
    render(<Select label="Risk Level" options={options} />);
    expect(screen.getByLabelText('Risk Level')).toHaveAttribute('id', 'risk-level');
  });

  it('reports value changes', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Select label="Priority" options={options} onChange={onChange} />);
    await user.selectOptions(screen.getByLabelText('Priority'), 'high');
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(screen.getByLabelText('Priority')).toHaveValue('high');
  });

  it('shows an error message when provided', () => {
    render(<Select label="Priority" options={options} error="Pick one" />);
    expect(screen.getByText('Pick one')).toBeInTheDocument();
  });

  it('renders no error element without an error prop', () => {
    render(<Select label="Priority" options={options} />);
    expect(screen.queryByText('Required')).not.toBeInTheDocument();
  });
});
