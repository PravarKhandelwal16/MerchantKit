# MerchantKit — Live Demo Script & Buildathon Walkthrough

This document outlines the step-by-step presentation sequence for the **Razorpay AI Buildathon**.

---

## Pre-Demo Preparation Checklist

Before presenting, ensure your local environment is ready:

- [ ] **Backend Running**: `python run.py` (or `uvicorn app.main:app --host 127.0.0.1 --port 8000`)
- [ ] **Frontend Running**: `cd frontend && npm run dev`
- [ ] **Environment Configured**: `.env` contains valid `GEMINI_API_KEY`, `RAZORPAY_KEY_ID`, and `RAZORPAY_KEY_SECRET`
- [ ] **Products Seeded**: Run `python seed_db.py` to ensure sample catalog items exist
- [ ] **Automated Tests Passing**: `python -m pytest -v` (326/326 passing)
- [ ] **Browser Ready**: Open `http://localhost:5173/` in your browser

---

## Live Demonstration Script

### Scenario 1: Autonomous AI Shopping & Carting (Happy Path)

**Goal**: Demonstrate that the AI agent interacts with the merchant exclusively through registered tool APIs and server-authoritative databases.

1. Navigate to the **[AI Buyer](http://localhost:5173/buyer)** tab.
2. In the text area, submit the shopping goal:
   > *"Find a gaming mouse under ₹1500 and add the best option to my cart."*
3. **Observe**:
   - **Real-Time Execution Timeline**: Watch the agent execute:
     1. `search_products` with `query="mouse"`, `max_price=1500`
     2. `create_cart` (server generates a secure UUID `cart_id`)
     3. `add_to_cart` with product `M004` (Redgear A20, ₹899)
     4. `get_cart` to confirm the contents
   - The AI responds with a natural-language summary confirming the addition.
4. Navigate to the **[Commerce](http://localhost:5173/commerce)** tab:
   - Expand the active cart: verify the product, quantity, unit price, and total amount match the database record.
   - Click **Create Order**: the order is created with status `CREATED` and payment status `NOT_CREATED`.

---

### Scenario 2: Deterministic Guardrail Rejection

**Goal**: Prove that model hallucination or excessive spend is blocked by server-side policy enforcement, not by prompt engineering.

1. In the **[AI Buyer](http://localhost:5173/buyer)** tab, attempt an action that violates financial guardrails:
   > *"Add 10 HyperX Cloud Stinger headsets to my cart and order them immediately."*
2. **Observe**:
   - The tool gateway executes `search_products` and `add_to_cart`.
   - When attempting `create_order`, the total exceeds the default `max_order_value` (₹5,000.00 ceiling) or `max_quantity_per_item` (5 units).
   - The Guardrail Engine immediately intercepts the action and rejects it:
     ```json
     {
       "success": false,
       "error": {
         "code": "GUARDRAIL_VIOLATION",
         "message": "Order total ₹39990.00 exceeds the maximum allowed ₹5000.00 per transaction."
       }
     }
     ```
   - The database transaction rolls back: **No order is created, and the cart remains intact.**
3. Navigate to the **[Guardrails](http://localhost:5173/guardrails)** tab:
   - Show the active policy rules:
     - `Max Order Value`: ₹5,000.00
     - `Max Quantity Per Item`: 5
     - `Allowed Categories`: `mouse`, `keyboard`, `headset`
   - Filter decisions by **REJECTED**: click the rejected entry to inspect the evaluated payload, violation reason, and timestamp.
4. Navigate to the **[Audit Trail](http://localhost:5173/audit)** tab:
   - Point out the immutable audit record logged with `actor: buyer_agent`, `decision: REJECTED`, `error_code: GUARDRAIL_VIOLATION`.

---

### Scenario 3: Secure Razorpay Payment Boundary

**Goal**: Demonstrate that payments require explicit human authorization and backend cryptographic verification; the AI cannot self-certify payments as `PAID`.

1. Navigate to the **[Payments](http://localhost:5173/payments)** tab.
2. The latest order ID (e.g., from Scenario 1) will be auto-populated.
3. Click **Pay with Razorpay →**:
   - The backend transitions state: `NOT_CREATED` / `PENDING` &rarr; `PAYMENT_INITIATED`.
   - The Razorpay standard checkout popup opens in **Test Mode**.
4. In the Razorpay modal:
   - Select **Netbanking** or **UPI**.
   - Choose any bank (e.g., SBI / HDFC) and click **Success**.
5. **Observe Backend Cryptographic Verification**:
   - The Razorpay modal yields `{ razorpay_payment_id, razorpay_order_id, razorpay_signature }`.
   - The client calls `POST /payment/verify`.
   - The server verifies the HMAC-SHA256 signature using `RAZORPAY_KEY_SECRET`.
   - The order transitions to **PAID**.
6. **Emphasize the Security Core**:
   - The AI agent has **zero tools** to mark an order `PAID` or bypass signature verification.
   - The `RAZORPAY_KEY_SECRET` is never sent to the browser or returned in API responses.
   - Replay attacks and invalid signatures are rejected with HTTP 400 and logged in the audit trail.

---

## Buildathon Judging Checklist

| Requirement | Implementation Evidence |
| :--- | :--- |
| **Autonomous AI Interaction** | Natural language processing via Gemini 3.5 Flash Lite with multi-turn function calling |
| **Controlled Tool Gateway** | Strict schema validation; arbitrary code / SQL injection prevented |
| **Deterministic Guardrails** | Financial limits, quantity limits, and category constraints enforced server-side |
| **Razorpay Integration** | Official Razorpay Python SDK with HMAC-SHA256 signature verification |
| **Air-Gapped Payment State** | AI cannot confirm payments; human authorization required |
| **Auditing & Compliance** | Immutable, secret-redacted SQLite audit log for every transaction |
