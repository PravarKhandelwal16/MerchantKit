import { useEffect, useState } from 'react';
import { PageHeader } from '../components/PageHeader';
import { StatusBadge } from '../components/StatusBadge';
import { EmptyState } from '../components/EmptyState';
import { getAuditTrail } from '../api/client';
import type { AuditEntry } from '../api/types';

function fmtTime(ts: string) {
  if (ts.length >= 19) return ts.slice(11, 19);
  return ts;
}

export function Overview() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getAuditTrail(8)
      .then((res) => {
        if (res.success && res.data) setEntries(res.data);
        else setError('Could not load activity.');
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <>
      <PageHeader
        title="Overview"
        description="System status and recent activity."
      />

      {/* Metric strip */}
      <div className="mb-8 grid grid-cols-4 gap-3">
        {[
          { label: 'Agent', value: 'Online' },
          { label: 'Guardrails', value: 'Active' },
          { label: 'Payment', value: 'Test Mode' },
          { label: 'Audit', value: 'Recording' },
        ].map(({ label, value }) => (
          <div key={label} className="rounded border border-slate-200 px-4 py-3">
            <p className="text-xs text-slate-500">{label}</p>
            <p className="mt-1 text-sm font-semibold text-slate-800">{value}</p>
          </div>
        ))}
      </div>

      {/* Recent activity */}
      <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-400">
        Recent Activity
      </p>

      {loading && <p className="text-sm text-slate-400">Loading…</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}

      {!loading && !error && entries.length === 0 && (
        <EmptyState
          message="No activity yet."
          hint="Use the AI Buyer to start a shopping session."
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
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
