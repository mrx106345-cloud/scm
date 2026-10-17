import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import Badge from './badge';

describe('Badge', () => {
  it('renders the success variant', () => {
    render(<Badge variant="success">Active</Badge>);
    expect(screen.getByText('Active')).toBeInTheDocument();
  });
});
