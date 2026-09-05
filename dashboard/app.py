"""
MerchantKit — Demo Dashboard
Presentation layer only. All authoritative operations remain in FastAPI.
"""
import os
import requests
import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BACKEND = os.getenv("BACKEND_BASE_URL", "http://localhost:8000")

st.set_page_config(
    page_title="MerchantKit",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');

:root {
    --bg-main: #ffffff;
    --bg-sidebar: #f8fafc;
    --text-primary: #1e293b;
    --text-secondary: #64748b;
    --border: #e2e8f0;
    --accent: #2563eb;
    --success: #16a34a;
    --error: #dc2626;
}

html, body, [class*="css"], .stApp, .stApp > div {
    font-family: 'Inter', sans-serif !important;
    background-color: var(--bg-main);
    color: var(--text-primary);
}

/* Hide chrome */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
header { visibility: hidden; }

/* Sidebar styling */
[data-testid="stSidebar"] {
    background-color: var(--bg-sidebar) !important;
    border-right: 1px solid var(--border);
}
[data-testid="stSidebarNav"] { display: none; }

.sidebar-title {
    font-size: 18px;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 2px;
}
.sidebar-subtitle {
    font-size: 12px;
    color: var(--text-secondary);
    margin-bottom: 24px;
}
.stRadio > div { gap: 4px; }
.stRadio label {
    padding: 8px 12px !important;
    border-radius: 6px;
    background: transparent !important;
    color: var(--text-secondary) !important;
    font-weight: 500;
    cursor: pointer;
}
.stRadio label:hover {
    background: #f1f5f9 !important;
    color: var(--text-primary) !important;
}
.stRadio label[data-checked="true"] {
    background: #eff6ff !important;
    color: var(--accent) !important;
}
.stRadio div[role="radio"] div:first-child { display: none; }

/* Main content */
.block-container {
    max-width: 1000px;
    padding-top: 2rem;
    padding-bottom: 3rem;
}

/* Header */
.header-container {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    border-bottom: 1px solid var(--border);
    padding-bottom: 16px;
    margin-bottom: 32px;
}
.page-title {
    font-size: 24px;
    font-weight: 600;
    margin: 0 0 4px 0;
    color: var(--text-primary);
}
.page-subtitle {
    font-size: 13px;
    color: var(--text-secondary);
    margin: 0;
}
.status-indicator {
    display: flex;
    gap: 16px;
    font-size: 12px;
    color: var(--text-secondary);
}
.status-dot {
    display: inline-block;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    margin-right: 6px;
    background-color: var(--success);
}
.status-dot.offline { background-color: var(--error); }
.status-dot.neutral { background-color: var(--text-secondary); }

/* AI Buyer */
.btn-primary > button {
    background: var(--accent) !important;
    color: white !important;
    border: none !important;
    border-radius: 6px !important;
    padding: 8px 16px !important;
    font-weight: 500 !important;
    font-size: 13px !important;
}
.conversation-block { margin-top: 28px; }
.msg-you { margin-bottom: 16px; }
.msg-you-label {
    font-size: 11px;
    text-transform: uppercase;
    font-weight: 600;
    color: var(--text-secondary);
    margin-bottom: 4px;
}
.msg-you-text {
    font-size: 14px;
    color: var(--text-primary);
    border-left: 2px solid var(--border);
    padding-left: 12px;
}
.msg-agent { margin-bottom: 24px; }
.msg-agent-label {
    font-size: 11px;
    text-transform: uppercase;
    font-weight: 600;
    color: var(--accent);
    margin-bottom: 4px;
}
.msg-agent-text {
    font-size: 14px;
    color: var(--text-primary);
    line-height: 1.6;
}

/* Timeline */
.tl-item { display: flex; margin-bottom: 14px; align-items: flex-start; }
.tl-step {
    font-size: 10px;
    font-weight: 600;
    color: var(--text-secondary);
    width: 22px; height: 22px;
    border-radius: 50%;
    border: 1px solid var(--border);
    display: flex; align-items: center; justify-content: center;
    margin-right: 10px;
    background: #f8fafc;
    flex-shrink: 0;
    margin-top: 1px;
}
.tl-content { display: flex; flex-direction: column; }
.tl-title { font-family: monospace; font-size: 13px; color: var(--text-primary); margin-bottom: 1px; }
.tl-status { font-size: 11px; font-weight: 500; }
.tl-status.success { color: var(--success); }
.tl-status.failed { color: var(--error); }
.tl-status.rejected { color: #d97706; }

/* Metric boxes */
.metric-box {
    padding: 12px 16px;
    border: 1px solid var(--border);
    border-radius: 6px;
    background: #ffffff;
}
.metric-label { font-size: 12px; color: var(--text-secondary); margin-bottom: 4px; }
.metric-val { font-size: 18px; font-weight: 600; color: var(--text-primary); }

/* Policy items */
.policy-item {
    border-bottom: 1px solid var(--border);
    padding: 12px 0;
    display: flex; justify-content: space-between;
}
.policy-item:last-child { border-bottom: none; }

/* Status pills */
.status-pill {
    display: inline-block; padding: 2px 8px;
    border-radius: 12px; font-size: 11px; font-weight: 500;
}
.status-pill.success { background: #dcfce7; color: #166534; }
.status-pill.error { background: #fee2e2; color: #991b1b; }
.status-pill.neutral { background: #f1f5f9; color: #475569; }

/* Inputs */
.stTextInput input {
    border: 1px solid var(--border) !important;
    border-radius: 6px !important;
    padding: 8px 12px !important;
}

/* Section label */
.section-label {
    font-size: 11px;
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 12px;
}

/* Empty state */
.empty-state {
    padding: 32px 0;
    text-align: center;
    color: var(--text-secondary);
    font-size: 14px;
}
.empty-state-hint {
    font-size: 12px;
    color: var(--text-secondary);
    margin-top: 4px;
    opacity: 0.7;
}

/* Divider */
.mk-divider {
    border: none;
    border-top: 1px solid var(--border);
    margin: 24px 0;
}

/* Session badge in sidebar */
.session-badge {
    font-family: monospace;
    font-size: 11px;
    color: var(--text-secondary);
    padding: 4px 8px;
    background: #f1f5f9;
    border-radius: 4px;
    word-break: break-all;
    margin-bottom: 4px;
}
.session-key {
    font-size: 10px;
    text-transform: uppercase;
    color: var(--text-secondary);
    margin-bottom: 2px;
    margin-top: 8px;
}

</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def api(method: str, path: str, timeout: int = 300, **kwargs):
    try:
        resp = requests.request(method, f"{BACKEND}{path}", timeout=timeout, **kwargs)
        return resp.json(), None
    except requests.exceptions.ConnectionError:
        return None, "Unable to connect to MerchantKit backend."
    except requests.exceptions.Timeout:
        return None, "Request timed out (local AI model took longer than 5 minutes)."
    except Exception as e:
        return None, f"Request error: {type(e).__name__}"

def backend_online() -> bool:
    data, _ = api("GET", "/health", timeout=3)
    return data is not None and data.get("status") == "ok"

def fmt_inr(v) -> str:
    try:
        return f"₹{float(v):,.2f}"
    except (TypeError, ValueError):
        return "—"

def fmt_time(ts: str) -> str:
    """Extract HH:MM:SS from ISO timestamp."""
    if not ts:
        return "—"
    if len(ts) >= 19:
        return ts[11:19]
    return ts

# ---------------------------------------------------------------------------
# Session state initialization
# ---------------------------------------------------------------------------
defaults = {
    "chat_history": [],        # list of {role, text} for conversation display
    "tool_log": [],            # list of tool call summaries from last run
    "cart_id": "",
    "order_id": "",
    "page": "Overview",
    "last_agent_run": None,    # timestamp of last agent run for cache busting
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown('<div class="sidebar-title">MerchantKit</div>', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-subtitle">AI Commerce Agent Gateway</div>', unsafe_allow_html=True)

    pages = ["Overview", "AI Buyer", "Commerce", "Guardrails", "Payments", "Audit Trail"]
    page = st.radio("Navigation", pages, label_visibility="collapsed")

    # Show current session context if available
    if st.session_state.cart_id or st.session_state.order_id:
        st.markdown("---")
        st.markdown('<div style="font-size:11px;font-weight:600;color:#64748b;text-transform:uppercase;margin-bottom:6px;">Current Session</div>', unsafe_allow_html=True)
        if st.session_state.cart_id:
            st.markdown('<div class="session-key">Cart</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="session-badge">{st.session_state.cart_id}</div>', unsafe_allow_html=True)
        if st.session_state.order_id:
            st.markdown('<div class="session-key">Order</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="session-badge">{st.session_state.order_id}</div>', unsafe_allow_html=True)
        if st.button("Clear Session", use_container_width=True):
            st.session_state.cart_id = ""
            st.session_state.order_id = ""
            st.session_state.chat_history = []
            st.session_state.tool_log = []
            st.rerun()

# ---------------------------------------------------------------------------
# Header (render once, shared across all pages)
# ---------------------------------------------------------------------------
be_ok = backend_online()

subtitles = {
    "Overview": "System status and recent activity.",
    "AI Buyer": "Interact with the merchant through a controlled AI agent.",
    "Commerce": "Inspect authoritative cart and order state.",
    "Guardrails": "Deterministic policy constraints and decisions.",
    "Payments": "Secure payment state management.",
    "Audit Trail": "Immutable record of all commerce actions."
}

status_html = f"""
<div class="status-indicator">
    <div><span class="status-dot {'offline' if not be_ok else ''}"></span>Agent {'Online' if be_ok else 'Offline'}</div>
    <div><span class="status-dot {'offline' if not be_ok else ''}"></span>Guardrails Active</div>
    <div><span class="status-dot neutral"></span>Test Mode</div>
</div>
"""

st.markdown(f"""
<div class="header-container">
    <div>
        <h1 class="page-title">{page}</h1>
        <p class="page-subtitle">{subtitles.get(page, "")}</p>
    </div>
    {status_html}
</div>
""", unsafe_allow_html=True)

if not be_ok:
    st.error("Unable to connect to MerchantKit backend. Start it with `python run.py`.")
    st.stop()


# ===========================================================================
# PAGE: OVERVIEW
# ===========================================================================
if page == "Overview":
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown('<div class="metric-box"><div class="metric-label">Agent</div><div class="metric-val">Online</div></div>', unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="metric-box"><div class="metric-label">Guardrails</div><div class="metric-val">Active</div></div>', unsafe_allow_html=True)
    with col3:
        st.markdown('<div class="metric-box"><div class="metric-label">Payment</div><div class="metric-val">Test Mode</div></div>', unsafe_allow_html=True)
    with col4:
        st.markdown('<div class="metric-box"><div class="metric-label">Audit</div><div class="metric-val">Recording</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="section-label">Recent Activity</div>', unsafe_allow_html=True)

    data, err = api("GET", "/dashboard/audit?limit=8")
    if err:
        st.error(err)
    elif data and data.get("success") and data["data"]:
        rows = []
        for e in data["data"]:
            dec = e.get("policy_decision")
            if dec not in ("APPROVED", "REJECTED"):
                dec = "—"
            status = "SUCCESS" if e.get("success") else e.get("error_code", "FAILED")
            rows.append({
                "Time": fmt_time(e.get("timestamp", "")),
                "Actor": e.get("actor", ""),
                "Action": e.get("action", ""),
                "Decision": dec,
                "Status": status,
            })
        df = pd.DataFrame(rows)

        def _color_status(val):
            if val == "SUCCESS": return "color: #16a34a; font-weight: 500;"
            if val in ("FAILED", "GUARDRAIL_VIOLATION", "INVALID_SIGNATURE"): return "color: #dc2626; font-weight: 500;"
            return ""
        st.dataframe(df.style.map(_color_status, subset=["Status"]), hide_index=True, use_container_width=True)
    else:
        st.markdown("""
        <div class="empty-state">
            No activity yet.
            <div class="empty-state-hint">Use the AI Buyer to start a shopping session.</div>
        </div>
        """, unsafe_allow_html=True)


# ===========================================================================
# PAGE: AI BUYER
# ===========================================================================
elif page == "AI Buyer":
    col_chat, col_exec = st.columns([6, 4], gap="large")

    with col_chat:
        user_input = st.text_area(
            "Request",
            placeholder='Find a gaming mouse under ₹1500 and add the best option to my cart.',
            height=100,
            label_visibility="collapsed",
        )

        st.markdown('<div class="btn-primary">', unsafe_allow_html=True)
        submit = st.button("Send Request →")
        st.markdown('</div>', unsafe_allow_html=True)

        if submit and user_input.strip():
            msg = user_input.strip()
            with st.spinner("Agent is working..."):
                data, err = api("POST", "/agent/chat", json={"message": msg})

            if err:
                st.error(f"AI Agent unavailable: {err}")
            elif data:
                # Append to conversation history
                st.session_state.chat_history.append({"role": "user", "text": msg})
                st.session_state.chat_history.append({"role": "agent", "text": data.get("message", "")})

                # Store tool log
                st.session_state.tool_log = data.get("tool_call_log", [])

                # Auto-populate session IDs from structured response
                session_data = data.get("session_data", {})
                if session_data.get("cart_id"):
                    st.session_state.cart_id = session_data["cart_id"]
                if session_data.get("order_id"):
                    st.session_state.order_id = session_data["order_id"]

                st.rerun()

        # Display conversation history
        if st.session_state.chat_history:
            st.markdown('<div class="conversation-block">', unsafe_allow_html=True)
            for turn in st.session_state.chat_history:
                if turn["role"] == "user":
                    st.markdown(f"""
                    <div class="msg-you">
                        <div class="msg-you-label">You</div>
                        <div class="msg-you-text">{turn["text"]}</div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div class="msg-agent">
                        <div class="msg-agent-label">Agent</div>
                        <div class="msg-agent-text">{turn["text"]}</div>
                    </div>
                    """, unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

            # Show auto-populated session context
            if st.session_state.cart_id or st.session_state.order_id:
                st.markdown("<hr class='mk-divider'>", unsafe_allow_html=True)
                hints = []
                if st.session_state.cart_id:
                    hints.append(f"Cart `{st.session_state.cart_id}` loaded in Commerce.")
                if st.session_state.order_id:
                    hints.append(f"Order `{st.session_state.order_id}` loaded in Commerce and Payments.")
                for h in hints:
                    st.caption(h)
        else:
            st.markdown("""
            <div class="empty-state">
                Send a request to get started.
                <div class="empty-state-hint">Example: "Find a gaming mouse under ₹1500 and add it to my cart."</div>
            </div>
            """, unsafe_allow_html=True)

    with col_exec:
        st.markdown('<div class="section-label">Agent Execution</div>', unsafe_allow_html=True)

        log = st.session_state.tool_log
        if log:
            tl_html = ""
            for i, entry in enumerate(log):
                tool = entry.get("tool_name", "unknown")
                ok = entry.get("success", False)
                err_val = entry.get("error")

                is_rejected = False
                if isinstance(err_val, dict):
                    is_rejected = err_val.get("code") == "GUARDRAIL_VIOLATION"
                elif isinstance(err_val, str):
                    is_rejected = "GUARDRAIL" in err_val.upper()

                status_class = "success" if ok else ("rejected" if is_rejected else "failed")
                status_text = "Completed" if ok else ("Rejected by guardrail" if is_rejected else "Failed")

                tl_html += f"""
                <div class="tl-item">
                    <div class="tl-step">{i+1:02d}</div>
                    <div class="tl-content">
                        <div class="tl-title">{tool}</div>
                        <div class="tl-status {status_class}">{status_text}</div>
                    </div>
                </div>
                """
            st.markdown(tl_html, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="empty-state" style="text-align:left;">
                Execution steps will appear here.
            </div>
            """, unsafe_allow_html=True)


# ===========================================================================
# PAGE: COMMERCE
# ===========================================================================
elif page == "Commerce":
    # Allow manual override of IDs, but pre-populate from session
    c1, c2 = st.columns(2)
    with c1:
        cart_id_input = st.text_input("Cart ID", value=st.session_state.cart_id, placeholder="e.g. cart-abc123")
        if cart_id_input != st.session_state.cart_id:
            st.session_state.cart_id = cart_id_input
    with c2:
        order_id_input = st.text_input("Order ID", value=st.session_state.order_id, placeholder="e.g. order-xyz789")
        if order_id_input != st.session_state.order_id:
            st.session_state.order_id = order_id_input

    st.markdown("<hr class='mk-divider'>", unsafe_allow_html=True)

    # Cart section
    if st.session_state.cart_id.strip():
        st.markdown('<div class="section-label">Current Cart</div>', unsafe_allow_html=True)
        data, err = api("GET", f"/dashboard/cart/{st.session_state.cart_id.strip()}")
        if err:
            st.error(err)
        elif not data or not data.get("success"):
            st.markdown("""
            <div class="empty-state">
                Cart not found.
                <div class="empty-state-hint">The cart ID may be incorrect or the cart may not exist.</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            cart = data["data"]
            items = cart.get("items", [])
            if items:
                rows = []
                for it in items:
                    rows.append({
                        "Product": it["product_id"],
                        "Qty": it["quantity"],
                        "Unit Price": fmt_inr(it["unit_price"]),
                        "Subtotal": fmt_inr(it["quantity"] * it["unit_price"]),
                    })
                st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
                # Backend-authoritative total: sum from backend data
                total = sum(it["quantity"] * it["unit_price"] for it in items)
                st.markdown(f"""
                <div style="margin-top:12px;padding:12px 16px;border:1px solid var(--border);border-radius:6px;display:flex;justify-content:space-between;align-items:center;">
                    <span style="font-size:13px;color:var(--text-secondary);">Authoritative Total</span>
                    <span style="font-size:16px;font-weight:600;">{fmt_inr(total)}</span>
                </div>
                """, unsafe_allow_html=True)
                st.markdown("<br>", unsafe_allow_html=True)

                # Create order from cart (if cart is ACTIVE and no order yet)
                cart_status = cart.get("status", "")
                if cart_status == "ACTIVE" and not st.session_state.order_id.strip():
                    st.markdown('<div class="section-label">Place Order</div>', unsafe_allow_html=True)
                    st.markdown('<div class="btn-primary">', unsafe_allow_html=True)
                    if st.button("Create Order from Cart"):
                        res, err = api("POST", "/tools/execute", json={
                            "tool": "create_order",
                            "arguments": {"cart_id": st.session_state.cart_id.strip()}
                        })
                        if err:
                            st.error(err)
                        elif res and res.get("success"):
                            order_data = res.get("data", {})
                            if hasattr(order_data, "get"):
                                oid = order_data.get("order_id")
                                if oid:
                                    st.session_state.order_id = oid
                                    st.success(f"Order created: `{oid}`")
                                    st.rerun()
                            else:
                                st.success("Order created. Check Payments tab.")
                                st.rerun()
                        else:
                            err_info = res.get("error", {}) if res else {}
                            if isinstance(err_info, dict):
                                st.error(f"Order creation failed: {err_info.get('message', 'Unknown error')}")
                            else:
                                st.error(f"Order creation failed: {err_info}")
                    st.markdown('</div>', unsafe_allow_html=True)
            else:
                st.markdown("""
                <div class="empty-state">
                    Cart is empty.
                    <div class="empty-state-hint">Use the AI Buyer to add products.</div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="empty-state">
            No cart loaded.
            <div class="empty-state-hint">Use the AI Buyer to create a cart, or enter a Cart ID above.</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<hr class='mk-divider'>", unsafe_allow_html=True)

    # Order section
    if st.session_state.order_id.strip():
        st.markdown('<div class="section-label">Order Details</div>', unsafe_allow_html=True)
        data, err = api("GET", f"/dashboard/order/{st.session_state.order_id.strip()}")
        if err:
            st.error(err)
        elif not data or not data.get("success"):
            st.markdown("""
            <div class="empty-state">
                Order not found.
                <div class="empty-state-hint">Create an order first using the cart above.</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            order = data["data"]
            m1, m2, m3 = st.columns(3)
            with m1:
                st.markdown(f'<div class="metric-box"><div class="metric-label">Total Amount</div><div class="metric-val">{fmt_inr(order["total_amount"])}</div></div>', unsafe_allow_html=True)
            with m2:
                st.markdown(f'<div class="metric-box"><div class="metric-label">Status</div><div class="metric-val">{order["status"]}</div></div>', unsafe_allow_html=True)
            with m3:
                p_status = order.get("payment_status") or "NOT_CREATED"
                st.markdown(f'<div class="metric-box"><div class="metric-label">Payment Status</div><div class="metric-val">{p_status}</div></div>', unsafe_allow_html=True)

            items = order.get("items", [])
            if items:
                st.markdown("<br>", unsafe_allow_html=True)
                rows = [{"Product": it["product_name"], "Qty": it["quantity"], "Unit Price": fmt_inr(it["unit_price"])} for it in items]
                st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


# ===========================================================================
# PAGE: GUARDRAILS
# ===========================================================================
elif page == "Guardrails":
    # Flow diagram
    st.markdown("""
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:28px;font-size:13px;color:var(--text-secondary);">
        <span style="padding:4px 10px;border:1px solid var(--border);border-radius:4px;color:var(--text-primary);font-weight:500;">AI Request</span>
        <span>→</span>
        <span style="padding:4px 10px;border:1px solid var(--border);border-radius:4px;color:var(--text-primary);font-weight:500;">Policy Check</span>
        <span>→</span>
        <span style="padding:4px 10px;background:#dcfce7;border:1px solid #bbf7d0;border-radius:4px;color:#166534;font-weight:500;">Approved</span>
        <span style="color:var(--border);">/</span>
        <span style="padding:4px 10px;background:#fee2e2;border:1px solid #fecaca;border-radius:4px;color:#991b1b;font-weight:500;">Rejected</span>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2, gap="large")

    with col1:
        st.markdown('<div class="section-label">Active Policies</div>', unsafe_allow_html=True)
        data, err = api("GET", "/dashboard/guardrails")
        if err:
            st.error(err)
        elif data and data.get("success"):
            p = data["data"]
            cats = ", ".join(c.title() for c in p.get("allowed_categories", []))
            st.markdown(f"""
            <div style="border:1px solid var(--border);border-radius:6px;padding:0 16px;">
                <div class="policy-item">
                    <span style="font-size:13px;color:var(--text-secondary);">Maximum Order Value</span>
                    <span style="font-size:14px;font-weight:500;">{fmt_inr(p['max_order_value'])}</span>
                </div>
                <div class="policy-item">
                    <span style="font-size:13px;color:var(--text-secondary);">Maximum Item Quantity</span>
                    <span style="font-size:14px;font-weight:500;">{p['max_item_quantity']}</span>
                </div>
                <div class="policy-item">
                    <span style="font-size:13px;color:var(--text-secondary);">Allowed Categories</span>
                    <span style="font-size:14px;font-weight:500;">{cats}</span>
                </div>
                <div class="policy-item">
                    <span style="font-size:13px;color:var(--text-secondary);">Payment Confirmation</span>
                    <span style="font-size:14px;font-weight:500;">{"Required" if p.get("require_payment_confirmation") else "Not required"}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.caption("Could not load policy configuration.")

    with col2:
        st.markdown('<div class="section-label">Recent Decisions</div>', unsafe_allow_html=True)
        audit_data, _ = api("GET", "/dashboard/audit?limit=100")
        decisions = []
        if audit_data and audit_data.get("success"):
            for e in audit_data["data"]:
                if e.get("policy_decision") in ("APPROVED", "REJECTED"):
                    decisions.append(e)
                    if len(decisions) >= 5:
                        break

        if decisions:
            for d in decisions:
                dec = d.get("policy_decision")
                cls = "success" if dec == "APPROVED" else "error"
                reason = d.get("reason") or ("Action allowed." if dec == "APPROVED" else "Action blocked.")
                st.markdown(f"""
                <div style="border:1px solid var(--border);border-radius:6px;padding:12px 16px;margin-bottom:8px;">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                        <span class="status-pill {cls}">{dec}</span>
                        <span style="font-size:11px;color:var(--text-secondary);font-family:monospace;">{fmt_time(d.get("timestamp",""))}</span>
                    </div>
                    <div style="font-size:13px;color:var(--text-primary);margin-bottom:2px;">{reason}</div>
                    <div style="font-size:11px;color:var(--text-secondary);font-family:monospace;">Action: {d.get("action","")}</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="empty-state" style="text-align:left;">
                No policy decisions yet.
                <div class="empty-state-hint">Use AI Buyer to trigger guardrail checks.</div>
            </div>
            """, unsafe_allow_html=True)


# ===========================================================================
# PAGE: PAYMENTS
# ===========================================================================
elif page == "Payments":
    order_id_input = st.text_input("Order ID", value=st.session_state.order_id, placeholder="e.g. order-xyz789")
    if order_id_input != st.session_state.order_id:
        st.session_state.order_id = order_id_input

    st.markdown("<hr class='mk-divider'>", unsafe_allow_html=True)

    if st.session_state.order_id.strip():
        resp, err = api("GET", f"/dashboard/order/{st.session_state.order_id.strip()}")
        if err:
            st.error(err)
        elif not resp or not resp.get("success"):
            st.markdown("""
            <div class="empty-state">
                Order not found.
                <div class="empty-state-hint">Create an order in the Commerce tab first.</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            order_data = resp["data"]
            pstatus = order_data.get("payment_status") or "NOT_CREATED"

            # Status colour
            pstatus_colors = {
                "PAID": ("#dcfce7", "#166534"),
                "FAILED": ("#fee2e2", "#991b1b"),
                "PAYMENT_INITIATED": ("#eff6ff", "#1d4ed8"),
                "PENDING": ("#fffbeb", "#92400e"),
                "NOT_CREATED": ("#f1f5f9", "#475569"),
            }
            bg, fg = pstatus_colors.get(pstatus, ("#f1f5f9", "#475569"))

            st.markdown(f"""
            <div style="border:1px solid var(--border);border-radius:6px;padding:24px;margin-top:8px;">
                <div style="font-size:11px;color:var(--text-secondary);text-transform:uppercase;font-weight:600;margin-bottom:8px;">Payment Status</div>
                <div style="display:inline-block;padding:6px 14px;background:{bg};color:{fg};border-radius:6px;font-size:20px;font-weight:600;margin-bottom:16px;">{pstatus}</div>

                <div style="font-size:13px;color:var(--text-secondary);margin-bottom:8px;display:flex;flex-direction:column;gap:4px;">
                    <span>Order Total: <strong style="color:var(--text-primary);">{fmt_inr(order_data.get("total_amount", 0))}</strong></span>
                    <span>Provider: <strong style="color:var(--text-primary);">Razorpay (Test Mode)</strong></span>
                    <span>Razorpay Order: <code style="font-size:12px;">{order_data.get("razorpay_order_id") or "—"}</code></span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            if pstatus == "PENDING":
                st.markdown('<div class="section-label">Checkout</div>', unsafe_allow_html=True)
                st.caption("The AI prepared the order. Initiating payment requires explicit user action.")
                st.markdown('<div class="btn-primary">', unsafe_allow_html=True)
                if st.button("Initiate Payment →"):
                    res, perr = api("POST", "/payment/initiate",
                                    json={"order_id": st.session_state.order_id.strip()})
                    if perr:
                        st.error(f"Payment service error: {perr}")
                    elif res and res.get("payment_status"):
                        st.success("Payment initiated. Status updated to PAYMENT_INITIATED.")
                        st.rerun()
                    else:
                        err_msg = res.get("error", "Unknown error") if res else "No response"
                        st.error(f"Payment initiation failed: {err_msg}")
                st.markdown('</div>', unsafe_allow_html=True)
            elif pstatus in ("NOT_CREATED",):
                st.info("Create an order in the Commerce tab to enable payment.")
            elif pstatus == "PAYMENT_INITIATED":
                st.info("Payment has been initiated. Complete the Razorpay checkout flow to confirm.")
            elif pstatus == "PAID":
                st.success("Payment has been verified and confirmed.")

            # Security note
            st.markdown("""
            <div style="margin-top:16px;padding:10px 14px;background:#f8fafc;border-left:3px solid var(--border);border-radius:0 4px 4px 0;">
                <div style="font-size:12px;color:var(--text-secondary);">
                    <strong style="color:var(--text-primary);">Security boundary:</strong>
                    The AI cannot set payment status to PAID. Payment verification requires
                    server-side cryptographic signature validation via POST /payment/verify.
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="empty-state">
            No order loaded.
            <div class="empty-state-hint">Create an order in the Commerce tab, or enter an Order ID above.</div>
        </div>
        """, unsafe_allow_html=True)


# ===========================================================================
# PAGE: AUDIT TRAIL
# ===========================================================================
elif page == "Audit Trail":
    # Refresh control
    col_hdr, col_btn = st.columns([8, 2])
    with col_hdr:
        st.markdown('<div class="section-label">All Events (newest first)</div>', unsafe_allow_html=True)
    with col_btn:
        if st.button("Refresh"):
            st.rerun()

    data, err = api("GET", "/dashboard/audit?limit=100")
    if err:
        st.error(err)
    elif data and data.get("success") and data["data"]:
        entries = data["data"]
        rows = []
        for e in entries:
            dec = e.get("policy_decision")
            if dec not in ("APPROVED", "REJECTED"):
                dec = "—"

            status = "SUCCESS" if e.get("success") else e.get("error_code", "FAILED")
            reason = e.get("reason") or "—"
            if len(reason) > 60:
                reason = reason[:60] + "…"

            rows.append({
                "Time": fmt_time(e.get("timestamp", "")),
                "Actor": e.get("actor", ""),
                "Action": e.get("action", ""),
                "Decision": dec,
                "Status": status,
                "Reason": reason,
            })

        df = pd.DataFrame(rows)

        def _color_status(val):
            if val == "SUCCESS": return "color: #16a34a; font-weight: 500;"
            if val in ("FAILED", "GUARDRAIL_VIOLATION", "INVALID_SIGNATURE"): return "color: #dc2626; font-weight: 500;"
            return ""

        def _color_decision(val):
            if val == "APPROVED": return "color: #16a34a;"
            if val == "REJECTED": return "color: #dc2626;"
            return "color: #94a3b8;"

        st.dataframe(
            df.style
              .map(_color_status, subset=["Status"])
              .map(_color_decision, subset=["Decision"]),
            hide_index=True,
            use_container_width=True,
        )
    else:
        st.markdown("""
        <div class="empty-state">
            No audit entries yet.
            <div class="empty-state-hint">All tool calls, guardrail decisions, and payment events appear here.</div>
        </div>
        """, unsafe_allow_html=True)
