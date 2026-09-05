import { useState } from 'react';
import { PageHeader } from '../components/PageHeader';
import { ExecutionTimeline } from '../components/ExecutionTimeline';
import { sendAgentMessage } from '../api/client';
import type { ToolCallSummary, SessionData } from '../api/types';

interface ChatTurn {
  role: 'user' | 'agent';
  text: string;
  stopReason?: string;
}

interface AiBuyerProps {
  /** Called after every successful agent response with extracted session IDs. */
  onSessionUpdate?: (session: SessionData) => void;
}

/**
 * Classify API errors into user-friendly messages.
 * Never exposes stack traces, config, or internal details.
 */
function classifyError(err: unknown): string {
  if (!(err instanceof Error)) return 'An unexpected error occurred. Please try again.';

  const msg = err.message;

  if (msg.includes('Cannot connect') || msg.includes('fetch')) {
    return 'Unable to connect to MerchantKit backend. Is it running?';
  }
  if (msg.includes('timed out')) {
    return 'The AI request took too long. The local model may still be processing — please wait a moment and try again.';
  }
  if (msg.includes('HTTP 5') || msg.includes('500') || msg.includes('502') || msg.includes('503')) {
    return 'AI service is temporarily unavailable. Please try again later.';
  }
  if (msg.includes('HTTP 4')) {
    return 'The request was rejected by the backend. Please check your input and try again.';
  }

  // Generic safe fallback — no raw exception text exposed
  return 'Unable to reach the AI Agent. Please try again.';
}

export function AiBuyer({ onSessionUpdate }: AiBuyerProps) {
  const [input, setInput] = useState('');
  const [history, setHistory] = useState<ChatTurn[]>([]);
  const [toolLog, setToolLog] = useState<ToolCallSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Structured session identifiers extracted from backend responses only.
  // Never parsed from natural-language text.
  const [_sessionData, setSessionData] = useState<SessionData>({ cart_id: null, order_id: null });

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const msg = input.trim();
    if (!msg || loading) return;

    // Reset per-request state immediately so the UI reflects the new request
    setLoading(true);
    setError(null);
    setToolLog([]);     // clear previous execution log before new request

    try {
      const res = await sendAgentMessage(msg);

      // Append conversation turns
      setHistory((prev) => [
        ...prev,
        { role: 'user',  text: msg },
        {
          role: 'agent',
          text: res.message,
          stopReason: res.stop_reason !== 'complete' ? res.stop_reason : undefined,
        },
      ]);

      // Update execution log with real tool_call_log from backend
      setToolLog(res.tool_call_log);

      // Store structured session identifiers only if structurally returned
      if (res.session_data) {
        setSessionData(res.session_data);
        onSessionUpdate?.(res.session_data);
      }

      // Clear input only on success
      setInput('');
    } catch (err) {
      setError(classifyError(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <PageHeader
        title="AI Buyer"
        description="Interact with the merchant through a controlled AI agent."
      />

      <div className="flex gap-8">
        {/* ── Left 60% ── */}
        <div className="flex-[6] min-w-0">

          {/* Input form */}
          <form onSubmit={handleSubmit} className="mb-6">
            <textarea
              id="ai-buyer-input"
              className="w-full resize-none rounded border border-slate-200 px-3 py-2.5 text-sm text-slate-800 placeholder-slate-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-slate-50 disabled:text-slate-400"
              rows={4}
              placeholder="Find a gaming mouse under ₹1500 and add the best option to my cart."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={loading}
            />
            <div className="mt-2 flex items-center gap-3">
              <button
                id="ai-buyer-submit"
                type="submit"
                disabled={loading || !input.trim()}
                className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loading ? 'Working…' : 'Send Request →'}
              </button>
              {loading && (
                <span className="text-xs text-slate-400">
                  Agent is processing request…
                </span>
              )}
            </div>
          </form>

          {/* Error banner — user-friendly, never raw */}
          {error && (
            <div className="mb-4 rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          {/* Conversation history */}
          {history.length > 0 && (
            <div className="space-y-5">
              {history.map((turn, idx) =>
                turn.role === 'user' ? (
                  <div key={idx}>
                    <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                      You
                    </p>
                    <p className="border-l-2 border-slate-200 pl-3 text-sm text-slate-700">
                      {turn.text}
                    </p>
                  </div>
                ) : (
                  <div key={idx}>
                    <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-blue-600">
                      Agent
                    </p>
                    <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-800">
                      {turn.text}
                    </p>
                    {/* Surface non-complete stop reasons (e.g. max_iterations) */}
                    {turn.stopReason && (
                      <p className="mt-1.5 text-[11px] text-amber-600">
                        Note: Agent stopped early ({turn.stopReason}).
                      </p>
                    )}
                  </div>
                )
              )}
            </div>
          )}

          {/* Empty state */}
          {history.length === 0 && !loading && (
            <div className="py-8 text-center">
              <p className="text-sm text-slate-400">Send a request to get started.</p>
              <p className="mt-1 text-xs text-slate-300">
                Example: "Find a gaming mouse under ₹1500 and add it to my cart."
              </p>
            </div>
          )}
        </div>

        {/* ── Right 40% ── */}
        <div className="flex-[4] min-w-0">
          <p className="mb-4 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
            Agent Execution
          </p>
          <ExecutionTimeline steps={toolLog} isRunning={loading} />

          {/* Show tool count after completion */}
          {!loading && toolLog.length > 0 && (
            <p className="mt-4 text-[11px] text-slate-400">
              {toolLog.length} tool call{toolLog.length !== 1 ? 's' : ''} executed
            </p>
          )}
        </div>
      </div>
    </>
  );
}
