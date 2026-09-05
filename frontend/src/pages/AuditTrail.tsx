import { useEffect, useState, useCallback } from 'react';
import { StatusBadge } from '../components/StatusBadge';
import { EmptyState } from '../components/EmptyState';
import { getAuditTrail } from '../api/client';
import type { AuditEntry } from '../api/types';

function fmtTime(ts: string) {
  if (ts.length >= 19) return ts.slice(11, 19);
  return ts;
}

export function AuditTrail() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    getAuditTrail(100)
      .then((res) => {
        if (res.success && res.data) setEntries(res.data);
        else setError('Could not load audit trail.');
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <>
      <div className="mb-8 flex items-center justify-between border-b border-slate-200 pb-4">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Audit Trail</h1>
          <p className="mt-0.5 text-sm text-slate-500">Immutable record of all commerce actions.</p>
        </div>
        <button
          onClick={load}
          disabled={loading}
          className="rounded border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-40"
        >
          Refresh
        </button>
      </div>

      {loading && <p className="text-sm text-slate-400">Loading…</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}

      {!loading && !error && entries.length === 0 && (
        <EmptyState
          message="No audit entries yet."
          hint="All tool calls, guardrail decisions, and payment events appear here."
        />
      )}

      {!loading && entries.length > 0 && (
        <div className="overflow-hidden rounded border border-slate-200">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-xs text-slate-500">
              <tr>
                <th className="px-4 py-2.5 text-left font-medium">Time</th>
                <th className="px-4 py-2.5 text-left font-medium">Actor</th>
                <th className="px-4 py-2.5 text-left font-medium">Action</th>
                <th className="px-4 py-2.5 text-left font-medium">Decision</th>
                <th className="px-4 py-2.5 text-left font-medium">Status</th>
                <th className="px-4 py-2.5 text-left font-medium">Reason</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {entries.map((e) => (
                <tr key={e.id} className="hover:bg-slate-50">
                  <td className="px-4 py-2.5 font-mono text-xs text-slate-500">{fmtTime(e.timestamp)}</td>
                  <td className="px-4 py-2.5 text-slate-700">{e.actor}</td>
                  <td className="px-4 py-2.5 font-mono text-xs text-slate-700">{e.action}</td>
                  <td className="px-4 py-2.5">
                    {e.policy_decision && e.policy_decision !== 'N/A'
                      ? <StatusBadge value={e.policy_decision} />
                      : <span className="text-slate-300">—</span>}
                  </td>
                  <td className="px-4 py-2.5">
                    <span className={`text-xs font-medium ${e.success ? 'text-emerald-600' : 'text-red-600'}`}>
                      {e.success ? 'SUCCESS' : e.error_code ?? 'FAILED'}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-xs text-slate-500 max-w-xs truncate" title={e.reason ?? ''}>
                    {e.reason ? (e.reason.length > 50 ? e.reason.slice(0, 50) + '…' : e.reason) : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
