import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import Modal from './modal';

describe('Modal', () => {
  afterEach(() => {
    document.body.style.overflow = '';
  });

  it('renders nothing when closed', () => {
    render(
      <Modal isOpen={false} onClose={vi.fn()} title="Confirm order">
        Body
      </Modal>,
    );
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('exposes an accessible dialog with title and description when open', () => {
    render(
      <Modal isOpen onClose={vi.fn()} title="Confirm order" description="Sends to supplier">
        Body
      </Modal>,
    );
    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(dialog).toHaveAttribute('aria-label', 'Confirm order');
    expect(screen.getByRole('heading', { name: 'Confirm order' })).toBeInTheDocument();
    expect(screen.getByText('Sends to supplier')).toBeInTheDocument();
    expect(screen.getByText('Body')).toBeInTheDocument();
  });

  it('locks body scroll while open and restores it on unmount', () => {
    const { unmount } = render(
      <Modal isOpen onClose={vi.fn()} title="Locked">
        Body
      </Modal>,
    );
    expect(document.body.style.overflow).toBe('hidden');
    unmount();
    expect(document.body.style.overflow).toBe('auto');
  });

  it('calls onClose from the close button', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(
      <Modal isOpen onClose={onClose} title="Bye">
        Body
      </Modal>,
    );
    await user.click(screen.getByRole('button', { name: 'Close modal' }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('hides the close button when showCloseButton is false', () => {
    render(
      <Modal isOpen onClose={vi.fn()} title="Silent" showCloseButton={false}>
        Body
      </Modal>,
    );
    expect(screen.queryByRole('button', { name: 'Close modal' })).not.toBeInTheDocument();
  });

  it('calls onClose on Escape', () => {
    const onClose = vi.fn();
    render(
      <Modal isOpen onClose={onClose} title="Escapable">
        Body
      </Modal>,
    );
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('calls onClose when the backdrop is clicked', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(
      <Modal isOpen onClose={onClose} title="Backdrop">
        Body
      </Modal>,
    );
    const backdrop = document.querySelector('.backdrop-blur-sm');
    expect(backdrop).not.toBeNull();
    await user.click(backdrop as Element);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('renders footer content and the requested size', () => {
    render(
      <Modal isOpen onClose={vi.fn()} title="Big" size="lg" footer={<button>Approve</button>}>
        Body
      </Modal>,
    );
    expect(screen.getByRole('button', { name: 'Approve' })).toBeInTheDocument();
    expect(screen.getByRole('dialog').querySelector('.max-w-lg')).not.toBeNull();
  });
});
