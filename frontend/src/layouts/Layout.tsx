import { NavLink, Outlet } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { checkHealth, getLLMHealth } from '../api/client';
import { StatusDot } from '../components/StatusDot';
import type { SessionData, LLMHealthResponse } from '../api/types';

const NAV_LINKS = [
  { to: '/',           label: 'Overview' },
  { to: '/ai-buyer',   label: 'AI Buyer' },
  { to: '/commerce',   label: 'Commerce' },
  { to: '/guardrails', label: 'Guardrails' },
  { to: '/payments',   label: 'Payments' },
  { to: '/audit',      label: 'Audit Trail' },
];

interface LayoutProps {
  session: SessionData;
  onClearSession: () => void;
}

export function Layout({ session, onClearSession }: LayoutProps) {
  const [online, setOnline] = useState<boolean | null>(null);
  const [llmInfo, setLlmInfo] = useState<LLMHealthResponse | null>(null);

  useEffect(() => {
    let cancelled = false;
    const poll = () => {
      checkHealth().then((ok) => { if (!cancelled) setOnline(ok); });
      getLLMHealth().then((info) => { if (!cancelled) setLlmInfo(info); });
    };
    poll();
    const interval = setInterval(poll, 15_000);
    return () => { cancelled = true; clearInterval(interval); };
  }, []);

  const navLinkClass = ({ isActive }: { isActive: boolean }) =>
    `block px-3 py-2 rounded text-sm font-medium transition-colors ${
      isActive
        ? 'bg-blue-50 text-blue-700'
        : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
    }`;

  const hasSession = session.cart_id || session.order_id;

  return (
    <div className="flex h-screen overflow-hidden bg-white">
      {/* ── Sidebar ── */}
      <aside className="flex w-52 shrink-0 flex-col border-r border-slate-200 bg-slate-50">
        {/* Brand */}
        <div className="border-b border-slate-200 px-4 py-5">
          <p className="text-sm font-semibold text-slate-900">MerchantKit</p>
          <p className="mt-0.5 text-xs text-slate-500">AI Commerce Agent Gateway</p>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto px-2 py-3">
          <ul className="space-y-0.5">
            {NAV_LINKS.map(({ to, label }) => (
              <li key={to}>
                <NavLink to={to} end={to === '/'} className={navLinkClass}>
                  {label}
                </NavLink>
              </li>
            ))}
          </ul>

          {/* Session context — only shown when IDs are available */}
          {hasSession && (
            <div className="mt-4 border-t border-slate-200 pt-4">
              <p className="mb-2 px-1 text-[10px] font-semibold uppercase tracking-wide text-slate-400">
                Session
              </p>
              {session.cart_id && (
                <div className="mb-1.5 px-1">
                  <p className="text-[10px] text-slate-400">Cart</p>
                  <p className="mt-0.5 truncate font-mono text-[11px] text-slate-600" title={session.cart_id}>
                    {session.cart_id.slice(0, 20)}…
                  </p>
                </div>
              )}
              {session.order_id && (
                <div className="mb-2 px-1">
                  <p className="text-[10px] text-slate-400">Order</p>
                  <p className="mt-0.5 truncate font-mono text-[11px] text-slate-600" title={session.order_id}>
                    {session.order_id.slice(0, 20)}…
                  </p>
                </div>
              )}
              <button
                onClick={onClearSession}
                className="mt-1 w-full rounded border border-slate-200 px-2 py-1.5 text-[11px] text-slate-500 hover:bg-white hover:text-slate-700"
              >
                Clear Session
              </button>
            </div>
          )}
        </nav>

        {/* Status footer */}
        <div className="border-t border-slate-200 px-4 py-3 space-y-1.5">
          <StatusDot
            online={online ?? false}
            label={online === null ? 'Connecting…' : online ? 'Agent Online' : 'Agent Offline'}
          />
          {llmInfo?.provider && (
            <div className="flex items-center gap-1.5 px-0.5 text-[11px] text-slate-500 font-medium">
              <span className="text-slate-400">Provider:</span>
              <span className="capitalize font-mono text-slate-700">{llmInfo.provider}</span>
              {llmInfo.status === 'offline' && (
                <span className="rounded bg-amber-100 px-1 py-0.2 text-[9px] text-amber-700">Unset</span>
              )}
            </div>
          )}
          <StatusDot online={online ?? false} label="Guardrails Active" />
          <StatusDot online={false} label="Test Mode" neutral />
        </div>
      </aside>

      {/* ── Main content ── */}
      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-4xl px-8 py-8">
          {online === false && (
            <div className="mb-6 rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              Cannot reach MerchantKit backend at{' '}
              <code className="font-mono text-xs">{import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'}</code>.
              Start it with <code className="font-mono text-xs">python run.py</code>.
            </div>
          )}
          <Outlet />
        </div>
      </main>
    </div>
  );
}
