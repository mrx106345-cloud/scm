import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';

export type Explanation = {
  alert_id: string;
  summary: string;
  why: string;
  suggested_action: string;
  source: 'llm' | 'template' | string;
  validator: string;
  facts: Record<string, unknown>;
};

async function fetchExplanation(alertId: string): Promise<Explanation> {
  const r = await fetch(`/api/v1/alerts/${encodeURIComponent(alertId)}/explanation`);
  if (!r.ok) throw new Error('explanation failed');
  return r.json();
}

/** Badge disclosing how the text was produced (Part M §4; H3 source field). */
export function ExplanationBadge({ source }: { source: string }) {
  const label = source === 'llm' ? 'AI-written' : 'template';
  return <span data-testid="explanation-badge">{label}</span>;
}

export function AlertExplanation({ alertId }: { alertId: string }) {
  const q = useQuery({
    queryKey: ['explanation', alertId],
    queryFn: () => fetchExplanation(alertId),
  });
  if (q.isLoading) return <p>Loading explanation…</p>;
  if (q.error) return <p>Explanation unavailable.</p>;
  const e = q.data!;
  return (
    <section aria-label="alert explanation">
      <ExplanationBadge source={e.source} />
      <p>{e.summary}</p>
      <p>{e.why}</p>
      <p>{e.suggested_action}</p>
    </section>
  );
}

export type ChatMessage = { role: 'user' | 'assistant'; text: string };

export type ChatResponse = {
  intent: string;
  entity: string | null;
  facts: Record<string, unknown>;
  table: Array<Record<string, unknown>>;
  supported_questions: string[];
};

async function postChat(question: string): Promise<ChatResponse> {
  const r = await fetch('/api/v1/chat/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  });
  if (!r.ok) throw new Error('chat failed');
  return r.json();
}

function renderReply(body: ChatResponse): string {
  if (body.intent === 'unknown') {
    return `Supported questions:\n${body.supported_questions.join('\n')}`;
  }
  const lines = body.table.map((row) => JSON.stringify(row));
  return [`intent=${body.intent}`, ...lines].join('\n');
}

/** Docked chat panel wired to POST /api/v1/chat/ask (Part M §9). */
export function ChatPanel() {
  const [input, setInput] = useState('');
  const [history, setHistory] = useState<ChatMessage[]>([]);
  const m = useMutation({
    mutationFn: postChat,
    onSuccess: (body, question) => {
      setHistory((h) => [
        ...h,
        { role: 'user', text: question },
        { role: 'assistant', text: renderReply(body) },
      ]);
    },
  });
  return (
    <aside aria-label="chat panel">
      <ul>
        {history.map((msg, i) => (
          <li key={i} data-testid={`chat-${msg.role}`}>
            {msg.text}
          </li>
        ))}
      </ul>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          const q = input.trim();
          if (q) {
            setInput('');
            m.mutate(q);
          }
        }}
      >
        <input aria-label="chat input" value={input} onChange={(e) => setInput(e.target.value)} />
        <button type="submit" disabled={m.isPending}>
          Send
        </button>
      </form>
      {m.isError && <p>Chat unavailable.</p>}
    </aside>
  );
}
