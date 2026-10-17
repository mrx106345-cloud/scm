import { describe, expect, it } from 'vitest';
import { render } from '@testing-library/react';
import Skeleton from './skeleton';

describe('Skeleton', () => {
  it('renders with the default rounded variant', () => {
    const { container } = render(<Skeleton />);
    expect(container.firstElementChild).toHaveClass('animate-pulse', 'bg-muted', 'rounded-md');
  });

  it.each([
    ['text', 'rounded'],
    ['circular', 'rounded-full'],
    ['rounded', 'rounded-md'],
  ] as const)('applies the %s variant', (variant, expected) => {
    const { container } = render(<Skeleton variant={variant} />);
    expect(container.firstElementChild).toHaveClass(expected);
  });

  it('applies width and height through inline styles', () => {
    const { container } = render(<Skeleton width="12rem" height="1rem" />);
    expect(container.firstElementChild).toHaveStyle({ width: '12rem', height: '1rem' });
  });

  it('is not interactive', () => {
    const { container } = render(<Skeleton />);
    expect(container.firstElementChild).toHaveClass('pointer-events-none');
  });
});
