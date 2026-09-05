import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { useState } from 'react';
import { Layout } from './layouts/Layout';
import { Overview } from './pages/Overview';
import { AiBuyer } from './pages/AiBuyer';
import { Commerce } from './pages/Commerce';
import { Guardrails } from './pages/Guardrails';
import { Payments } from './pages/Payments';
import { AuditTrail } from './pages/AuditTrail';
import type { SessionData } from './api/types';

/**
 * Session state is lifted to App level so cart_id and order_id discovered
 * by the AI Buyer are automatically available in Commerce and Payments.
 *
 * IDs are ONLY populated from structured backend responses (session_data field).
 * They are NEVER parsed from natural-language agent text.
 */
export default function App() {
  const [session, setSession] = useState<SessionData>({ cart_id: null, order_id: null });

  function handleSessionUpdate(updated: SessionData) {
    setSession((prev) => ({
      cart_id: updated.cart_id ?? prev.cart_id,
      order_id: updated.order_id ?? prev.order_id,
    }));
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout session={session} onClearSession={() => setSession({ cart_id: null, order_id: null })} />}>
          <Route index element={<Overview />} />
          <Route path="/ai-buyer" element={<AiBuyer onSessionUpdate={handleSessionUpdate} />} />
          <Route path="/commerce" element={<Commerce initialCartId={session.cart_id ?? ''} initialOrderId={session.order_id ?? ''} />} />
          <Route path="/guardrails" element={<Guardrails />} />
          <Route path="/payments" element={<Payments initialOrderId={session.order_id ?? ''} />} />
          <Route path="/audit" element={<AuditTrail />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
