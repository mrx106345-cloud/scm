import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import Button from './button';

describe('Button', () => {
  it('renders children', () => {
    render(<Button>Save</Button>);
    expect(screen.getByRole('button', { name: 'Save' })).toBeInTheDocument();
  });

  it('is disabled while loading', () => {
    render(<Button isLoading>Saving</Button>);
    expect(screen.getByRole('button', { name: 'Saving' })).toBeDisabled();
  });

  it('forwards clicks when enabled', async () => {
    const user = userEvent.setup();
    let clicks = 0;
    render(
      <Button
        onClick={() => {
          clicks += 1;
        }}
      >
        Go
      </Button>,
    );
    await user.click(screen.getByRole('button', { name: 'Go' }));
    expect(clicks).toBe(1);
  });
});
