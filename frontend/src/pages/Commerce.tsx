import { useEffect, useState, useCallback } from 'react';
import { StatusBadge } from '../components/StatusBadge';
import { getProducts, getCarts, getOrders } from '../api/commerce';
import type { Product, Cart, Order } from '../api/types';

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

interface CommerceProps {
  initialCartId?: string;
  initialOrderId?: string;
}

export function Commerce({ initialCartId = '', initialOrderId = '' }: CommerceProps) {
  const [products, setProducts] = useState<Product[]>([]);
  const [carts, setCarts] = useState<Cart[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [expandedCartIds, setExpandedCartIds] = useState<Set<string>>(new Set());
  const [expandedOrderIds, setExpandedOrderIds] = useState<Set<string>>(new Set());

  // Auto-expand initial IDs if passed from session
  useEffect(() => {
    if (initialCartId) {
      setExpandedCartIds((prev) => new Set([...prev, initialCartId]));
    }
  }, [initialCartId]);

  useEffect(() => {
    if (initialOrderId) {
      setExpandedOrderIds((prev) => new Set([...prev, initialOrderId]));
    }
  }, [initialOrderId]);

  const loadCommerceData = useCallback(async (isRefresh = false) => {
    if (isRefresh) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setError(null);

    try {
      const [prodRes, cartRes, orderRes] = await Promise.all([
        getProducts(),
        getCarts(50),
        getOrders(50),
      ]);

      if (prodRes.success && prodRes.data) {
        setProducts(prodRes.data);
      }
      if (cartRes.success && cartRes.data) {
        setCarts(cartRes.data);
      }
      if (orderRes.success && orderRes.data) {
        setOrders(orderRes.data);
      }
    } catch {
      setError('Unable to load commerce data.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadCommerceData();
  }, [loadCommerceData]);

  function toggleCart(id: string) {
    setExpandedCartIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleOrder(id: string) {
    setExpandedOrderIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  const isOverallEmpty =
    !loading && !error && products.length === 0 && carts.length === 0 && orders.length === 0;

  return (
    <div>
      {/* Header bar */}
      <div className="mb-8 flex items-start justify-between border-b border-slate-200 pb-4">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Commerce</h1>
          <p className="mt-0.5 text-sm text-slate-500">
            Products, carts and orders managed through the merchant gateway.
          </p>
        </div>
        <button
          id="commerce-refresh-btn"
          onClick={() => loadCommerceData(true)}
          disabled={loading || refreshing}
          className="inline-flex items-center gap-1.5 rounded border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50 transition-colors shadow-xs"
        >
          {refreshing ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>

      {/* Loading state */}
      {loading && (
        <div className="py-12 text-center" id="commerce-loading">
          <p className="text-sm text-slate-500">Loading commerce data...</p>
        </div>
      )}

      {/* Backend unavailable / error state */}
      {error && !loading && (
        <div className="mb-6 rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700" id="commerce-error">
          {error}
        </div>
      )}

      {/* Overall empty state */}
      {isOverallEmpty && (
        <div className="rounded border border-slate-200 py-12 text-center" id="commerce-empty">
          <p className="text-sm font-medium text-slate-700">No commerce activity yet.</p>
          <p className="mt-1 text-xs text-slate-400">
            Products, carts, and orders will appear here as activity occurs.
          </p>
        </div>
      )}

      {!loading && !error && !isOverallEmpty && (
        <div className="space-y-8">
          {/* ================================================================ */}
          {/* SECTION 1: PRODUCTS                                             */}
          {/* ================================================================ */}
          <section id="products-section">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Products
              </h2>
              <span className="text-xs text-slate-400">
                {products.length} {products.length === 1 ? 'item' : 'items'}
              </span>
            </div>

            {products.length === 0 ? (
              <div className="rounded border border-slate-200 py-8 text-center">
                <p className="text-sm text-slate-500">No products available.</p>
              </div>
            ) : (
              <div className="overflow-hidden rounded border border-slate-200">
                <table className="w-full text-sm">
                  <thead className="border-b border-slate-200 bg-slate-50 text-xs font-medium text-slate-500">
                    <tr>
                      <th className="px-4 py-2.5 text-left">Product Name</th>
                      <th className="px-4 py-2.5 text-left">Category</th>
                      <th className="px-4 py-2.5 text-right">Price</th>
                      <th className="px-4 py-2.5 text-right">Stock Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {products.map((p) => {
                      const inStock = p.stock > 0;
                      return (
                        <tr key={p.product_id} className="hover:bg-slate-50/50">
                          <td className="px-4 py-2.5 font-medium text-slate-800">
                            <div>{p.name}</div>
                            {p.description && (
                              <div className="text-xs font-normal text-slate-400">{p.description}</div>
                            )}
                          </td>
                          <td className="px-4 py-2.5 text-slate-600 capitalize">{p.category}</td>
                          <td className="px-4 py-2.5 text-right font-medium text-slate-800">
                            {fmtINR(p.price)}
                          </td>
                          <td className="px-4 py-2.5 text-right">
                            {inStock ? (
                              <span className="inline-block rounded border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700">
                                In Stock ({p.stock})
                              </span>
                            ) : (
                              <span className="inline-block rounded border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs font-medium text-slate-500">
                                Out of Stock
                              </span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          {/* ================================================================ */}
          {/* SECTION 2: ACTIVE CARTS                                         */}
          {/* ================================================================ */}
          <section id="carts-section">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Active Carts
              </h2>
              <span className="text-xs text-slate-400">
                {carts.length} {carts.length === 1 ? 'cart' : 'carts'}
              </span>
            </div>

            {carts.length === 0 ? (
              <div className="rounded border border-slate-200 py-8 text-center">
                <p className="text-sm text-slate-500">No active carts.</p>
                <p className="mt-1 text-xs text-slate-400">
                  Carts created by the AI Buyer will appear here.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {carts.map((cart) => {
                  const isExpanded = expandedCartIds.has(cart.cart_id);
                  const isSessionCart = initialCartId === cart.cart_id;

                  return (
                    <div
                      key={cart.cart_id}
                      className={`overflow-hidden rounded border transition-colors ${
                        isSessionCart
                          ? 'border-blue-300 ring-1 ring-blue-300 bg-blue-50/10'
                          : 'border-slate-200 bg-white'
                      }`}
                    >
                      {/* Cart summary header */}
                      <div
                        onClick={() => toggleCart(cart.cart_id)}
                        className="flex cursor-pointer items-center justify-between px-4 py-3 hover:bg-slate-50"
                      >
                        <div className="flex items-center gap-3">
                          <span className="text-xs text-slate-400">
                            {isExpanded ? '▼' : '▶'}
                          </span>
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="font-mono text-xs font-medium text-slate-800">
                                {cart.cart_id}
                              </span>
                              {isSessionCart && (
                                <span className="rounded bg-blue-100 px-1.5 py-0.5 text-[10px] font-medium text-blue-700">
                                  Current Session
                                </span>
                              )}
                            </div>
                            <p className="mt-0.5 text-xs text-slate-400">
                              Created {fmtDate(cart.created_at)}
                            </p>
                          </div>
                        </div>

                        <div className="flex items-center gap-4">
                          <div className="text-right">
                            <span className="text-xs text-slate-500">
                              {cart.total_quantity} {cart.total_quantity === 1 ? 'item' : 'items'}
                            </span>
                            <div className="text-sm font-semibold text-slate-800">
                              {fmtINR(cart.subtotal)}
                            </div>
                          </div>
                          <StatusBadge value={cart.status} />
                        </div>
                      </div>

                      {/* Expanded Cart Items */}
                      {isExpanded && (
                        <div className="border-t border-slate-200 bg-slate-50/50 p-4">
                          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
                            Cart Items
                          </p>
                          {cart.items.length === 0 ? (
                            <p className="text-xs text-slate-400 italic">Cart has no items.</p>
                          ) : (
                            <div className="overflow-hidden rounded border border-slate-200 bg-white">
                              <table className="w-full text-xs">
                                <thead className="border-b border-slate-200 bg-slate-50 text-slate-500">
                                  <tr>
                                    <th className="px-3 py-2 text-left font-medium">Product</th>
                                    <th className="px-3 py-2 text-center font-medium">Qty</th>
                                    <th className="px-3 py-2 text-right font-medium">Unit Price</th>
                                    <th className="px-3 py-2 text-right font-medium">Line Total</th>
                                  </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-100">
                                  {cart.items.map((item) => (
                                    <tr key={item.product_id} className="hover:bg-slate-50/50">
                                      <td className="px-3 py-2 text-slate-800">
                                        <div className="font-medium">
                                          {item.product_name || item.product_id}
                                        </div>
                                        {item.product_name && (
                                          <div className="font-mono text-[10px] text-slate-400">
                                            {item.product_id}
                                          </div>
                                        )}
                                      </td>
                                      <td className="px-3 py-2 text-center text-slate-700">
                                        {item.quantity}
                                      </td>
                                      <td className="px-3 py-2 text-right text-slate-700">
                                        {fmtINR(item.unit_price)}
                                      </td>
                                      <td className="px-3 py-2 text-right font-medium text-slate-800">
                                        {fmtINR(item.quantity * item.unit_price)}
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                              <div className="flex items-center justify-between border-t border-slate-200 bg-slate-50 px-3 py-2.5">
                                <span className="text-xs font-medium text-slate-600">
                                  Authoritative Total
                                </span>
                                <span className="text-sm font-semibold text-slate-900">
                                  {fmtINR(cart.subtotal)}
                                </span>
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </section>

          {/* ================================================================ */}
          {/* SECTION 3: ORDERS                                               */}
          {/* ================================================================ */}
          <section id="orders-section">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Orders
              </h2>
              <span className="text-xs text-slate-400">
                {orders.length} {orders.length === 1 ? 'order' : 'orders'}
              </span>
            </div>

            {orders.length === 0 ? (
              <div className="rounded border border-slate-200 py-8 text-center">
                <p className="text-sm text-slate-500">No orders placed yet.</p>
                <p className="mt-1 text-xs text-slate-400">
                  Confirmed orders created through the gateway flow will appear here.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {orders.map((order) => {
                  const isExpanded = expandedOrderIds.has(order.order_id);
                  const isSessionOrder = initialOrderId === order.order_id;

                  return (
                    <div
                      key={order.order_id}
                      className={`overflow-hidden rounded border transition-colors ${
                        isSessionOrder
                          ? 'border-blue-300 ring-1 ring-blue-300 bg-blue-50/10'
                          : 'border-slate-200 bg-white'
                      }`}
                    >
                      {/* Order summary header */}
                      <div
                        onClick={() => toggleOrder(order.order_id)}
                        className="flex cursor-pointer items-center justify-between px-4 py-3 hover:bg-slate-50"
                      >
                        <div className="flex items-center gap-3">
                          <span className="text-xs text-slate-400">
                            {isExpanded ? '▼' : '▶'}
                          </span>
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="font-mono text-xs font-medium text-slate-800">
                                {order.order_id}
                              </span>
                              {isSessionOrder && (
                                <span className="rounded bg-blue-100 px-1.5 py-0.5 text-[10px] font-medium text-blue-700">
                                  Current Session
                                </span>
                              )}
                            </div>
                            <p className="mt-0.5 text-xs text-slate-400">
                              Created {fmtDate(order.created_at)} · Currency: {order.currency}
                            </p>
                          </div>
                        </div>

                        <div className="flex items-center gap-4">
                          <div className="text-right">
                            <span className="text-xs text-slate-500">
                              {order.items.length} {order.items.length === 1 ? 'item' : 'items'}
                            </span>
                            <div className="text-sm font-semibold text-slate-800">
                              {fmtINR(order.total_amount)}
                            </div>
                          </div>
                          <StatusBadge value={order.status} />
                        </div>
                      </div>

                      {/* Expanded Order Items */}
                      {isExpanded && (
                        <div className="border-t border-slate-200 bg-slate-50/50 p-4">
                          <div className="mb-3 flex items-center justify-between">
                            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                              Order Details
                            </p>
                            <div className="flex items-center gap-2 text-xs">
                              <span className="text-slate-500">Payment:</span>
                              <StatusBadge value={order.payment_status ?? 'NOT_CREATED'} />
                            </div>
                          </div>

                          {order.items.length === 0 ? (
                            <p className="text-xs text-slate-400 italic">Order has no item records.</p>
                          ) : (
                            <div className="overflow-hidden rounded border border-slate-200 bg-white">
                              <table className="w-full text-xs">
                                <thead className="border-b border-slate-200 bg-slate-50 text-slate-500">
                                  <tr>
                                    <th className="px-3 py-2 text-left font-medium">Product</th>
                                    <th className="px-3 py-2 text-center font-medium">Qty</th>
                                    <th className="px-3 py-2 text-right font-medium">Unit Price</th>
                                    <th className="px-3 py-2 text-right font-medium">Line Total</th>
                                  </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-100">
                                  {order.items.map((item) => (
                                    <tr key={item.product_id} className="hover:bg-slate-50/50">
                                      <td className="px-3 py-2 text-slate-800 font-medium">
                                        {item.product_name}
                                      </td>
                                      <td className="px-3 py-2 text-center text-slate-700">
                                        {item.quantity}
                                      </td>
                                      <td className="px-3 py-2 text-right text-slate-700">
                                        {fmtINR(item.unit_price)}
                                      </td>
                                      <td className="px-3 py-2 text-right font-medium text-slate-800">
                                        {fmtINR(item.quantity * item.unit_price)}
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                              <div className="flex items-center justify-between border-t border-slate-200 bg-slate-50 px-3 py-2.5">
                                <span className="text-xs font-medium text-slate-600">
                                  Order Total ({order.currency})
                                </span>
                                <span className="text-sm font-semibold text-slate-900">
                                  {fmtINR(order.total_amount)}
                                </span>
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
