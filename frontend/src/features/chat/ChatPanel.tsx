import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { toast } from 'react-hot-toast';
import Modal from '@/components/ui/modal';
import Input from '@/components/ui/input';
import Button from '@/components/ui/button';

// ChatPanel - slides in from the right showing AI chat
// (Replaces explainChat.tsx in new feature folder structure)
export function ChatPanel({ isOpen = false }: { isOpen?: boolean; onClose?: () => void }) {
  const [message, setMessage] = useState('');
  const [isExpanded, setIsExpanded] = useState(isOpen);

  // Fetch recent alerts as suggested topics
  const { data: alerts = [], isLoading: alertsLoading } = useQuery<
    { id: string; type: string; severity: string; title: string; description: string }[]
  >({
    queryKey: ['/api/alerts'],
    queryFn: async () => {
      const res = await fetch('/api/alerts');
      if (!res.ok) throw new Error('Failed to fetch alerts');
      return res.json();
    },
    staleTime: 30000,
  });

  // Send message mutation
  const sendMutation = useMutation({
    mutationFn: async (text: string) => {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
      });
      if (!res.ok) throw new Error('Failed to send message');
      return res.json();
    },
    onSuccess: () => {
      // Update local state or refetch as needed
      toast.success('Message sent');
    },
    onError: (err) => {
      toast.error(err instanceof Error ? err.message : 'Failed to send message');
    },
  });

  const handleSend = (e: React.FormEvent) => {
    e.preventDefault();
    if (!message.trim()) return;
    sendMutation.mutate(message);
    setMessage('');
  };

  return (
    <>
      <button
        className="fixed bottom-4 right-4 z-40 flex h-12 w-12 items-center justify-center rounded-full bg-primary text-primary-foreground hover:bg-primary/90 transition-colors shadow-lg"
        onClick={() => setIsExpanded(true)}
        aria-label="Open chat"
      >
        <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
          />
        </svg>
      </button>

      <Modal
        isOpen={isExpanded}
        onClose={() => setIsExpanded(false)}
        title="AI Supply Chain Assistant"
        size="lg"
        footer={
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setIsExpanded(false)}>
              Close
            </Button>
            <Button
              isLoading={sendMutation.isPending}
              onClick={handleSend}
              disabled={!message.trim()}
            >
              Send
            </Button>
          </div>
        }
      >
        {/* Suggested topics */}
        <div className="mb-4 space-y-2">
          <p className="text-xs font-semibold text-muted-foreground uppercase">Recent Alerts</p>
          {alertsLoading ? (
            <p className="text-sm text-muted-foreground">Loading alerts...</p>
          ) : (
            alerts.slice(0, 4).map((alert) => (
              <button
                key={alert.id}
                className="mb-1 flex w-full items-start gap-2 rounded px-2 py-1.5 text-left text-sm hover:bg-accent transition-colors"
              >
                <span
                  className={`mt-1 h-2 w-2 shrink-0 rounded-full ${
                    alert.severity === 'critical'
                      ? 'bg-error'
                      : alert.severity === 'warning'
                        ? 'bg-warning'
                        : 'bg-info'
                  }`}
                />
                <span>{alert.title}</span>
              </button>
            ))
          )}
        </div>

        {/* Message list */}
        <div className="mb-4 max-h-[250px] overflow-y-auto space-y-2">
          {/* Messages will be rendered here */}
          <div className="text-sm text-muted-foreground">
            {sendMutation.isPending
              ? 'Assistant is thinking...'
              : 'Type your question about suppliers, inventory, or supply chain.'}
          </div>
        </div>

        {/* Input area */}
        <form onSubmit={handleSend} className="flex gap-2">
          <Input
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="Ask about stock levels, supplier delays, forecasts..."
            disabled={sendMutation.isPending}
            className="flex-1"
          />
          <Button type="submit" isLoading={sendMutation.isPending} disabled={!message.trim()}>
            Send
          </Button>
        </form>
        <p className="mt-2 text-xs text-muted-foreground">
          AI assistant powered by local model. Answers may be non-deterministic.
        </p>
      </Modal>
    </>
  );
}
