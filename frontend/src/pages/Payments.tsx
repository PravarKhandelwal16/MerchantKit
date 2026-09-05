import { useState } from 'react';
import { PageHeader } from '../components/PageHeader';
import { StatusBadge } from '../components/StatusBadge';
import { EmptyState } from '../components/EmptyState';
import { getOrder, initiatePayment } from '../api/client';
import type { Order } from '../api/types';

function fmtINR(v: number) {
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(v);
}

interface PaymentsProps {
  initialOrderId?: string;
}

export function Payments({ initialOrderId = '' }: PaymentsProps) {
  const [orderId, setOrderId] = useState(initialOrderId);
  const [order, setOrder] = useState<Order | null>(null);
  const [orderErr, setOrderErr] = useState<string | null>(null);
  const [orderLoading, setOrderLoading] = useState(false);
  const [paymentLoading, setPaymentLoading] = useState(false);
  const [paymentMsg, setPaymentMsg] = useState<string | null>(null);
  const [paymentErr, setPaymentErr] = useState<string | null>(null);

  function loadOrder() {
    if (!orderId.trim()) return;
    setOrderLoading(true);
    setOrderErr(null);
    setOrder(null);
    setPaymentMsg(null);
    setPaymentErr(null);
    getOrder(orderId.trim())
      .then((res) => {
        if (res.success && res.data) setOrder(res.data);
        else setOrderErr(res.error ?? 'Order not found.');
      })
      .catch((e: Error) => setOrderErr(e.message))
      .finally(() => setOrderLoading(false));
  }

  async function handleInitiatePayment() {
    if (!orderId.trim()) return;
    setPaymentLoading(true);
    setPaymentErr(null);
    setPaymentMsg(null);
    try {
      const res = await initiatePayment(orderId.trim());
      if (res.success) {
        setPaymentMsg('Payment initiated. Status updated to PAYMENT_INITIATED.');
        // Reload order to show updated state
        loadOrder();
      } else {
        setPaymentErr(res.error ?? 'Payment initiation failed.');
      }
    } catch (err) {
      setPaymentErr(err instanceof Error ? err.message : 'Payment initiation failed.');
    } finally {
      setPaymentLoading(false);
    }
  }

  const pStatus = order?.payment_status ?? 'NOT_CREATED';

  return (
    <>
      <PageHeader title="Payments" description="Secure payment state management." />

      <div className="mb-6">
        <label className="mb-1 block text-xs font-medium text-slate-500">Order ID</label>
        <div className="flex gap-2">
          <input
            className="w-80 rounded border border-slate-200 px-3 py-2 text-sm text-slate-800 placeholder-slate-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            placeholder="order-xyz789"
            value={orderId}
            onChange={(e) => setOrderId(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && loadOrder()}
          />
          <button
            onClick={loadOrder}
            disabled={!orderId.trim() || orderLoading}
            className="rounded border border-slate-200 px-3 py-2 text-xs font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-40"
          >
            Load
          </button>
        </div>
      </div>

      <hr className="mb-6 border-slate-200" />

      {orderLoading && <p className="text-sm text-slate-400">Loading order…</p>}
      {orderErr && <p className="text-sm text-red-600">{orderErr}</p>}

      {!orderLoading && !orderErr && !order && (
        <EmptyState
          message="No order loaded."
          hint="Create an order in Commerce, or enter an Order ID above."
        />
      )}

      {order && (
        <>
          <div className="mb-6 rounded border border-slate-200 p-5">
            <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">Payment Status</p>
            <div className="mb-4">
              <StatusBadge value={pStatus} />
            </div>
            <div className="space-y-1.5 text-sm text-slate-600">
              <p>Order Total: <span className="font-medium text-slate-800">{fmtINR(order.total_amount)}</span></p>
              <p>Provider: <span className="font-medium text-slate-800">Razorpay (Test Mode)</span></p>
              <p>Razorpay Order:{' '}
                <code className="text-xs text-slate-500">{order.razorpay_order_id ?? '—'}</code>
              </p>
            </div>
          </div>

          {/* Actions by state */}
          {pStatus === 'PENDING' && (
            <div className="mb-4">
              <p className="mb-2 text-xs text-slate-500">
                The AI prepared the order. Initiating payment requires explicit user action.
              </p>
              <button
                onClick={handleInitiatePayment}
                disabled={paymentLoading}
                className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
              >
                {paymentLoading ? 'Initiating…' : 'Initiate Payment →'}
              </button>
            </div>
          )}

          {pStatus === 'NOT_CREATED' && (
            <p className="text-sm text-slate-500">Create an order in Commerce to enable payment.</p>
          )}
          {pStatus === 'PAYMENT_INITIATED' && (
            <p className="text-sm text-slate-600">Payment has been initiated. Complete the Razorpay checkout to confirm.</p>
          )}
          {pStatus === 'PAID' && (
            <p className="text-sm text-emerald-600 font-medium">Payment has been verified and confirmed.</p>
          )}

          {paymentMsg && (
            <p className="mt-3 text-sm text-emerald-600">{paymentMsg}</p>
          )}
          {paymentErr && (
            <p className="mt-3 text-sm text-red-600">{paymentErr}</p>
          )}

          {/* Security note */}
          <div className="mt-6 border-l-2 border-slate-200 pl-4">
            <p className="text-xs text-slate-500">
              <span className="font-medium text-slate-700">Security boundary:</span>{' '}
              The AI cannot set payment status to PAID. Payment verification requires server-side
              cryptographic signature validation via{' '}
              <code className="text-[11px]">POST /payment/verify</code>.
            </p>
          </div>
        </>
      )}
    </>
  );
}
