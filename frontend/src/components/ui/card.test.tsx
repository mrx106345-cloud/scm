import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from './card';

describe('Card', () => {
  it('renders children inside a styled container', () => {
    const { container } = render(<Card>Body text</Card>);
    expect(screen.getByText('Body text')).toBeInTheDocument();
    expect(container.firstElementChild).toHaveClass('rounded-lg', 'bg-card', 'border-border');
  });

  it('adds hover styles only when hoverable', () => {
    const { container, rerender } = render(<Card>One</Card>);
    expect(container.firstElementChild).not.toHaveClass('hover:shadow-md');
    rerender(<Card hoverable>Two</Card>);
    expect(container.firstElementChild).toHaveClass('hover:shadow-md', 'transition-shadow');
  });

  it('merges a custom className', () => {
    const { container } = render(<Card className="mt-4">C</Card>);
    expect(container.firstElementChild).toHaveClass('mt-4', 'rounded-lg');
  });
});

describe('Card sections', () => {
  it('renders header, title, description, content and footer', () => {
    render(
      <Card>
        <CardHeader>
          <CardTitle>Suppliers</CardTitle>
          <CardDescription>At risk this week</CardDescription>
        </CardHeader>
        <CardContent>Content body</CardContent>
        <CardFooter>Footer bits</CardFooter>
      </Card>,
    );
    expect(screen.getByRole('heading', { name: 'Suppliers' })).toBeInTheDocument();
    expect(screen.getByText('At risk this week')).toBeInTheDocument();
    expect(screen.getByText('Content body')).toBeInTheDocument();
    expect(screen.getByText('Footer bits')).toBeInTheDocument();
  });
});
