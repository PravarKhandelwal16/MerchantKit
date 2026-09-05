import { useEffect, useState, useCallback } from 'react';
import { StatusBadge } from '../components/StatusBadge';
import { EmptyState } from '../components/EmptyState';
import { getGuardrailPolicy, getAuditTrail, getAllowedTools } from '../api/guardrails';
import type { GuardrailPolicy, AuditEntry, ToolDefinition } from '../api/types';

function fmtINR(v: number) {
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(v);
}

function fmtDate(isoStr: string) {
  try {
    const d = new Date(isoStr);
    if (isNaN(d.getTime())) return isoStr;
    return d.toLocaleString('en-IN', {
      dateStyle: 'medium',
      timeStyle: 'short',
    });
  } catch {
    return isoStr;
  }
}

function getPolicyCode(entry: AuditEntry): string {
  if (entry.result) {
    if ('total_amount' in entry.result && 'max_order_value' in entry.result) {
      return 'ORDER_VALUE_EXCEEDED';
    }
    if ('quantity' in entry.result && 'max_quantity_per_item' in entry.result) {
      return 'QUANTITY_EXCEEDED';
    }
    if ('category' in entry.result && 'allowed_categories' in entry.result) {
      return 'CATEGORY_NOT_ALLOWED';
    }
    if ('require_payment_confirmation' in entry.result) {
      return 'PAYMENT_CONFIRMATION_REQUIRED';
    }
  }
  if (entry.reason) {
    const lower = entry.reason.toLowerCase();
    if (lower.includes('order total') || lower.includes('maximum allowed') || lower.includes('limit')) {
      return 'ORDER_VALUE_EXCEEDED';
    }
    if (lower.includes('quantity')) {
      return 'QUANTITY_EXCEEDED';
    }
    if (lower.includes('category')) {
      return 'CATEGORY_NOT_ALLOWED';
    }
    if (lower.includes('confirmation')) {
      return 'PAYMENT_CONFIRMATION_REQUIRED';
    }
  }
  return entry.error_code ?? 'GUARDRAIL_VIOLATION';
}

function isRejected(entry: AuditEntry): boolean {
  return entry.policy_decision === 'REJECTED' || (!entry.success && entry.error_code === 'GUARDRAIL_VIOLATION');
}

export function Guardrails() {
  const [policy, setPolicy] = useState<GuardrailPolicy | null>(null);
  const [decisions, setDecisions] = useState<AuditEntry[]>([]);
  const [tools, setTools] = useState<ToolDefinition[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Selected decision for detailed inspection
  const [selectedDecisionId, setSelectedDecisionId] = useState<number | null>(null);
  const [decisionFilter, setDecisionFilter] = useState<'ALL' | 'REJECTED' | 'ALLOWED'>('ALL');

  const loadData = useCallback(async (isRefresh = false) => {
    if (isRefresh) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setError(null);

    try {
      const [policyRes, auditRes, toolsRes] = await Promise.all([
        getGuardrailPolicy(),
        getAuditTrail(100),
        getAllowedTools(),
      ]);

      if (policyRes.success && policyRes.data) {
        setPolicy(policyRes.data);
      } else {
        throw new Error('Policy data unavailable');
      }

      if (auditRes.success && auditRes.data) {
        setDecisions(auditRes.data);
        // Auto-select the first rejected decision if any, otherwise first decision
        const firstRejected = auditRes.data.find(isRejected);
        if (firstRejected) {
          setSelectedDecisionId(firstRejected.id);
        } else if (auditRes.data.length > 0) {
          setSelectedDecisionId(auditRes.data[0].id);
        }
      }

      if (toolsRes.success && toolsRes.data) {
        setTools(toolsRes.data);
      }
    } catch {
      setError('Unable to load guardrail data.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Filtered decisions based on user selection
  const filteredDecisions = decisions.filter((d) => {
    if (decisionFilter === 'REJECTED') return isRejected(d);
    if (decisionFilter === 'ALLOWED') return !isRejected(d);
    return true;
  });

  const selectedDecision = decisions.find((d) => d.id === selectedDecisionId) ?? null;

  return (
    <div>
      {/* Header bar */}
      <div className="mb-8 flex items-start justify-between border-b border-slate-200 pb-4">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Guardrails</h1>
          <p className="mt-0.5 text-sm text-slate-500">
            Deterministic policies that control what the AI agent is allowed to execute.
          </p>
        </div>
        <button
          onClick={() => loadData(true)}
          disabled={loading || refreshing}
          className="flex items-center gap-1.5 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 shadow-sm transition hover:bg-slate-50 disabled:opacity-50"
        >
          <span className={`inline-block ${refreshing ? 'animate-spin' : ''}`}>↻</span>
          {refreshing ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>

      {/* Error state */}
      {error && (
        <div className="mb-6 flex items-center justify-between rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          <span>{error}</span>
          <button
            onClick={() => loadData()}
            className="rounded bg-red-100 px-2.5 py-1 text-xs font-medium text-red-800 hover:bg-red-200"
          >
            Retry
          </button>
        </div>
      )}

      {/* Architecture Explanation Panel */}
      <div className="mb-8 rounded-xl border border-slate-200 bg-slate-50/70 p-4">
        <div className="mb-3 flex items-center justify-between">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
            Enforcement Architecture — Deterministic Security Boundary
          </p>
          <span className="rounded bg-indigo-50 px-2 py-0.5 text-[11px] font-medium text-indigo-700 border border-indigo-200">
            Authoritative Python Gate
          </span>
        </div>

        <div className="grid grid-cols-1 gap-2 sm:grid-cols-4">
          <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-xs">
            <div className="text-[10px] font-bold tracking-wider text-slate-400 uppercase">Step 1</div>
            <div className="mt-1 text-xs font-semibold text-slate-900">AI Request</div>
            <p className="mt-1 text-[11px] leading-relaxed text-slate-500">
              Agent proposes a structured tool call. No direct DB or payment access.
            </p>
          </div>

          <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-xs">
            <div className="text-[10px] font-bold tracking-wider text-slate-400 uppercase">Step 2</div>
            <div className="mt-1 text-xs font-semibold text-slate-900">Tool Gateway</div>
            <p className="mt-1 text-[11px] leading-relaxed text-slate-500">
              Validates registered tool schema, normalizes and redacts arguments.
            </p>
          </div>

          <div className="rounded-lg border border-indigo-200 bg-indigo-50/40 p-3 shadow-xs">
            <div className="text-[10px] font-bold tracking-wider text-indigo-600 uppercase">Step 3</div>
            <div className="mt-1 text-xs font-semibold text-indigo-950">Deterministic Policy</div>
            <p className="mt-1 text-[11px] leading-relaxed text-indigo-800">
              Enforces hard limits against backend DB state before any write.
            </p>
          </div>

          <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-xs">
            <div className="text-[10px] font-bold tracking-wider text-slate-400 uppercase">Step 4</div>
            <div className="mt-1 text-xs font-semibold text-slate-900">Allowed / Rejected</div>
            <p className="mt-1 text-[11px] leading-relaxed text-slate-500">
              Executes or halts; every decision is written to append-only audit log.
            </p>
          </div>
        </div>
      </div>

      {/* Main Grid: Left (Policies + Tools), Right (Decisions + Inspector) */}
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-12">
        {/* Left Column: Rules & Tools (5 cols) */}
        <div className="space-y-8 lg:col-span-5">
          {/* Active Policies Section */}
          <div className="rounded-lg border border-slate-200 bg-white shadow-xs">
            <div className="border-b border-slate-100 px-4 py-3">
              <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Active Policies
              </h2>
            </div>

            {loading && !policy ? (
              <div className="p-6 text-center text-sm text-slate-400">Loading policy rules…</div>
            ) : policy ? (
              <div className="divide-y divide-slate-100">
                <div className="flex items-start justify-between px-4 py-3">
                  <div>
                    <div className="text-sm font-medium text-slate-900">Max Order Value</div>
                    <div className="text-xs text-slate-500">Per-transaction checkout ceiling</div>
                  </div>
                  <div className="text-right">
                    <span className="text-sm font-semibold text-slate-800">
                      {fmtINR(policy.max_order_value)}
                    </span>
                    <div className="mt-0.5">
                      <StatusBadge value="ACTIVE" />
                    </div>
                  </div>
                </div>

                <div className="flex items-start justify-between px-4 py-3">
                  <div>
                    <div className="text-sm font-medium text-slate-900">Max Item Quantity</div>
                    <div className="text-xs text-slate-500">Single line item quantity limit</div>
                  </div>
                  <div className="text-right">
                    <span className="text-sm font-semibold text-slate-800">
                      {policy.max_item_quantity} units
                    </span>
                    <div className="mt-0.5">
                      <StatusBadge value="ACTIVE" />
                    </div>
                  </div>
                </div>

                <div className="flex items-start justify-between px-4 py-3">
                  <div>
                    <div className="text-sm font-medium text-slate-900">Allowed Categories</div>
                    <div className="text-xs text-slate-500">Permitted product categories</div>
                  </div>
                  <div className="text-right">
                    <div className="flex flex-wrap justify-end gap-1">
                      {policy.allowed_categories.map((c) => (
                        <span
                          key={c}
                          className="rounded bg-slate-100 px-2 py-0.5 font-mono text-xs font-medium text-slate-700"
                        >
                          {c}
                        </span>
                      ))}
                    </div>
                    <div className="mt-1">
                      <StatusBadge value="ACTIVE" />
                    </div>
                  </div>
                </div>

                <div className="flex items-start justify-between px-4 py-3">
                  <div>
                    <div className="text-sm font-medium text-slate-900">Payment Confirmation</div>
                    <div className="text-xs text-slate-500">Explicit confirmation before money movement</div>
                  </div>
                  <div className="text-right">
                    <span className="text-sm font-semibold text-slate-800">
                      {policy.require_payment_confirmation ? 'Required' : 'Optional'}
                    </span>
                    <div className="mt-0.5">
                      <StatusBadge value="ACTIVE" />
                    </div>
                  </div>
                </div>
              </div>
            ) : null}
          </div>

          {/* Registered Tools Section */}
          <div className="rounded-lg border border-slate-200 bg-white shadow-xs">
            <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
              <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Tool Allowlist
              </h2>
              <span className="font-mono text-xs text-slate-400">
                {tools.length} Registered
              </span>
            </div>

            {loading && tools.length === 0 ? (
              <div className="p-6 text-center text-sm text-slate-400">Loading allowed tools…</div>
            ) : (
              <div className="max-h-[380px] divide-y divide-slate-100 overflow-y-auto">
                {tools.map((t) => (
                  <div key={t.name} className="px-4 py-2.5 transition hover:bg-slate-50/50">
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs font-medium text-indigo-700">
                        {t.name}
                      </span>
                      <StatusBadge value="ALLOWED" />
                    </div>
                    <p className="mt-0.5 text-xs text-slate-500 line-clamp-2">
                      {t.description}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Decisions & Details Inspector (7 cols) */}
        <div className="space-y-6 lg:col-span-7">
          {/* Recent Decisions Section */}
          <div className="rounded-lg border border-slate-200 bg-white shadow-xs">
            <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
              <div>
                <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Recent Policy Decisions
                </h2>
              </div>

              {/* Filter Tabs */}
              <div className="flex rounded-md bg-slate-100 p-0.5 text-xs">
                <button
                  onClick={() => setDecisionFilter('ALL')}
                  className={`rounded px-2.5 py-1 font-medium transition ${
                    decisionFilter === 'ALL'
                      ? 'bg-white text-slate-900 shadow-xs'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  All ({decisions.length})
                </button>
                <button
                  onClick={() => setDecisionFilter('REJECTED')}
                  className={`rounded px-2.5 py-1 font-medium transition ${
                    decisionFilter === 'REJECTED'
                      ? 'bg-white text-red-700 shadow-xs'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  Rejected ({decisions.filter(isRejected).length})
                </button>
                <button
                  onClick={() => setDecisionFilter('ALLOWED')}
                  className={`rounded px-2.5 py-1 font-medium transition ${
                    decisionFilter === 'ALLOWED'
                      ? 'bg-white text-emerald-700 shadow-xs'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  Allowed ({decisions.filter((d) => !isRejected(d)).length})
                </button>
              </div>
            </div>

            {loading && decisions.length === 0 ? (
              <div className="p-8 text-center text-sm text-slate-400">Loading audit records…</div>
            ) : filteredDecisions.length === 0 ? (
              <div className="p-6">
                <EmptyState
                  message={
                    decisionFilter === 'REJECTED'
                      ? 'No rejected actions recorded.'
                      : 'No recent policy decisions.'
                  }
                  hint="Use AI Buyer or execute commerce operations to generate real policy decisions."
                />
              </div>
            ) : (
              <div className="max-h-[340px] divide-y divide-slate-100 overflow-y-auto">
                {filteredDecisions.map((d) => {
                  const rejected = isRejected(d);
                  const isSelected = selectedDecisionId === d.id;

                  return (
                    <div
                      key={d.id}
                      onClick={() => setSelectedDecisionId(d.id)}
                      className={`cursor-pointer px-4 py-3 transition ${
                        isSelected
                          ? 'bg-slate-50 ring-1 ring-inset ring-slate-300'
                          : 'hover:bg-slate-50/50'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <StatusBadge value={rejected ? 'REJECTED' : 'ALLOWED'} />
                          <span className="font-mono text-xs font-semibold text-slate-800">
                            {d.action}
                          </span>
                        </div>
                        <span className="font-mono text-[11px] text-slate-400">
                          {fmtDate(d.timestamp)}
                        </span>
                      </div>

                      <p className="mt-1 text-xs text-slate-600">
                        {d.reason ?? (rejected ? 'Action blocked by policy.' : 'Action permitted.')}
                      </p>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Action Details / Rejection Inspector Panel */}
          {selectedDecision && (
            <div
              className={`rounded-lg border p-5 shadow-xs transition ${
                isRejected(selectedDecision)
                  ? 'border-red-200 bg-red-50/20'
                  : 'border-slate-200 bg-white'
              }`}
            >
              <div className="flex items-start justify-between border-b border-slate-100 pb-3">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
                      Decision Details
                    </span>
                    <StatusBadge
                      value={isRejected(selectedDecision) ? 'REJECTED' : 'ALLOWED'}
                    />
                  </div>
                  <h3 className="mt-1 font-mono text-sm font-semibold text-slate-900">
                    {selectedDecision.action}
                  </h3>
                </div>
                <div className="text-right">
                  <div className="font-mono text-[11px] text-slate-400">
                    Log #{selectedDecision.id}
                  </div>
                  <div className="text-xs text-slate-500">
                    Actor: <span className="font-mono text-slate-700">{selectedDecision.actor}</span>
                  </div>
                </div>
              </div>

              {/* Policy Code & Reason */}
              <div className="mt-4 space-y-3">
                <div>
                  <span className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                    Policy Code
                  </span>
                  <div className="mt-0.5">
                    <span
                      className={`inline-block rounded px-2 py-0.5 font-mono text-xs font-semibold ${
                        isRejected(selectedDecision)
                          ? 'bg-red-100 text-red-800 border border-red-200'
                          : 'bg-emerald-100 text-emerald-800 border border-emerald-200'
                      }`}
                    >
                      {getPolicyCode(selectedDecision)}
                    </span>
                  </div>
                </div>

                <div>
                  <span className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                    Policy Reason
                  </span>
                  <p className="mt-0.5 text-xs leading-relaxed text-slate-800">
                    {selectedDecision.reason ?? 'No detailed reason recorded.'}
                  </p>
                </div>

                {/* Structured Values (Safe) */}
                {selectedDecision.result && typeof selectedDecision.result === 'object' && (
                  <div>
                    <span className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                      Evaluated Policy Parameters
                    </span>
                    <div className="mt-1.5 grid grid-cols-2 gap-2 rounded-lg border border-slate-200 bg-white p-3 text-xs">
                      {'total_amount' in selectedDecision.result && (
                        <div>
                          <div className="text-slate-400">Requested Total:</div>
                          <div className="font-semibold text-slate-900">
                            {fmtINR(Number(selectedDecision.result.total_amount))}
                          </div>
                        </div>
                      )}
                      {'max_order_value' in selectedDecision.result && (
                        <div>
                          <div className="text-slate-400">Maximum Allowed:</div>
                          <div className="font-semibold text-slate-900">
                            {fmtINR(Number(selectedDecision.result.max_order_value))}
                          </div>
                        </div>
                      )}
                      {'quantity' in selectedDecision.result && (
                        <div>
                          <div className="text-slate-400">Requested Quantity:</div>
                          <div className="font-semibold text-slate-900">
                            {String(selectedDecision.result.quantity)}
                          </div>
                        </div>
                      )}
                      {'max_quantity_per_item' in selectedDecision.result && (
                        <div>
                          <div className="text-slate-400">Max Allowed Quantity:</div>
                          <div className="font-semibold text-slate-900">
                            {String(selectedDecision.result.max_quantity_per_item)}
                          </div>
                        </div>
                      )}
                      {'category' in selectedDecision.result && (
                        <div>
                          <div className="text-slate-400">Requested Category:</div>
                          <div className="font-semibold text-slate-900">
                            {String(selectedDecision.result.category)}
                          </div>
                        </div>
                      )}
                      {'allowed_categories' in selectedDecision.result && (
                        <div>
                          <div className="text-slate-400">Allowed Categories:</div>
                          <div className="font-semibold text-slate-900">
                            {Array.isArray(selectedDecision.result.allowed_categories)
                              ? selectedDecision.result.allowed_categories.join(', ')
                              : String(selectedDecision.result.allowed_categories)}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Safe Arguments */}
                {selectedDecision.arguments && Object.keys(selectedDecision.arguments).length > 0 && (
                  <div>
                    <span className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                      Tool Arguments (Redacted)
                    </span>
                    <div className="mt-1 flex flex-wrap gap-2">
                      {Object.entries(selectedDecision.arguments).map(([k, v]) => (
                        <div
                          key={k}
                          className="rounded border border-slate-200 bg-white px-2.5 py-1 font-mono text-[11px]"
                        >
                          <span className="text-slate-400">{k}:</span>{' '}
                          <span className="font-semibold text-slate-700">
                            {typeof v === 'object' ? JSON.stringify(v) : String(v)}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Deterministic Boundary Note */}
                {isRejected(selectedDecision) && (
                  <div className="mt-3 rounded border border-red-200 bg-red-50 p-2.5 text-[11px] text-red-700">
                    <span className="font-semibold">Security Boundary Guaranteed:</span> Tool
                    execution was blocked deterministically at the gateway before any state transition
                    or database record was created.
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
