import { describe, expect, it, vi, afterEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AlertExplanation, ChatPanel } from './explainChat';

afterEach(() => {
  vi.unstubAllGlobals();
});

function wrap(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

function mockJson(payload: unknown, ok = true) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({ ok, json: async () => payload }) as Response),
  );
}

describe('AlertExplanation badge', () => {
  it('badges a template explanation', async () => {
    mockJson({
      alert_id: 'a1',
      summary: 'Hex Bolt M8 at S1 may run out in 0 days.',
      why: 'Alpha Steels takes 14 days to deliver with 350.00 at risk.',
      suggested_action: 'Order 0 units now.',
      source: 'template',
      validator: 'fail',
      facts: {},
    });
    wrap(<AlertExplanation alertId="a1" />);
    await waitFor(() =>
      expect(screen.getByTestId('explanation-badge')).toHaveTextContent('template'),
    );
  });

  it('badges an LLM explanation', async () => {
    mockJson({
      alert_id: 'a1',
      summary: 's',
      why: 'w',
      suggested_action: 'a',
      source: 'llm',
      validator: 'pass',
      facts: {},
    });
    wrap(<AlertExplanation alertId="a1" />);
    await waitFor(() =>
      expect(screen.getByTestId('explanation-badge')).toHaveTextContent('AI-written'),
    );
  });
});

describe('ChatPanel', () => {
  it('renders tabular fact rows from /chat/ask', async () => {
    const user = userEvent.setup();
    mockJson({
      intent: 'list_alerts',
      entity: 'severity=critical',
      facts: { total: 1 },
      table: [{ severity: 'critical', item_sku: 'HB-M8' }],
      supported_questions: [],
    });
    wrap(<ChatPanel />);
    await user.type(screen.getByLabelText('chat input'), 'List critical alerts');
    await user.click(screen.getByRole('button', { name: 'Send' }));
    await waitFor(() => expect(screen.getByTestId('chat-assistant')).toBeInTheDocument());
    expect(screen.getByTestId('chat-assistant').textContent).toContain('HB-M8');
  });

  it('lists supported questions for unknown intents', async () => {
    const user = userEvent.setup();
    mockJson({
      intent: 'unknown',
      entity: null,
      facts: {},
      table: [],
      supported_questions: [
        'How is item <sku/name> doing? (item_status)',
        'List critical/high alerts (list_alerts)',
      ],
    });
    wrap(<ChatPanel />);
    await user.type(screen.getByLabelText('chat input'), "What's the weather?");
    await user.click(screen.getByRole('button', { name: 'Send' }));
    await waitFor(() => expect(screen.getByTestId('chat-assistant')).toBeInTheDocument());
    expect(screen.getByTestId('chat-assistant').textContent).toContain('Supported questions');
  });
});
