"""
MerchantKit — Demo Dashboard
Presentation layer only. All data flows through the FastAPI backend.
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
[data-testid="stSidebarNav"] {
    display: none;
}
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
.stRadio > div {
    gap: 4px;
}
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
/* Hide the radio button circle */
.stRadio div[role="radio"] div:first-child { display: none; }

/* Main content width constraints */
.block-container {
    max-width: 1000px;
    padding-top: 2rem;
    padding-bottom: 3rem;
}

/* Header & Status */
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

/* AI Buyer Interface */
.chat-input {
    background: #ffffff;
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 12px;
    margin-bottom: 12px;
    font-size: 14px;
}
.btn-primary > button {
    background: var(--accent) !important;
    color: white !important;
    border: none !important;
    border-radius: 6px !important;
    padding: 8px 16px !important;
    font-weight: 500 !important;
    font-size: 13px !important;
}
.conversation-block {
    margin-top: 32px;
}
.msg-you {
    margin-bottom: 16px;
}
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
.msg-agent {
    margin-bottom: 24px;
}
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
    line-height: 1.5;
}

/* Timeline */
.timeline {
    margin-top: 16px;
}
.tl-item {
    display: flex;
    margin-bottom: 16px;
}
.tl-step {
    font-size: 10px;
    font-weight: 600;
    color: var(--text-secondary);
    width: 24px;
    height: 24px;
    border-radius: 50%;
    border: 1px solid var(--border);
    display: flex;
    align-items: center;
    justify-content: center;
    margin-right: 12px;
    background: #f8fafc;
    flex-shrink: 0;
}
.tl-content {
    display: flex;
    flex-direction: column;
}
.tl-title {
    font-family: monospace;
    font-size: 13px;
    color: var(--text-primary);
    margin-bottom: 2px;
}
.tl-status {
    font-size: 11px;
    font-weight: 500;
}
.tl-status.success { color: var(--success); }
.tl-status.failed { color: var(--error); }
.tl-status.rejected { color: #d97706; }

/* Tables and Data */
.stDataFrame {
    border: 1px solid var(--border);
    border-radius: 6px;
}
.metric-box {
    padding: 12px 16px;
    border: 1px solid var(--border);
    border-radius: 6px;
    background: #ffffff;
}
.metric-label {
    font-size: 12px;
    color: var(--text-secondary);
    margin-bottom: 4px;
}
.metric-val {
    font-size: 18px;
    font-weight: 600;
    color: var(--text-primary);
}
.policy-item {
    border-bottom: 1px solid var(--border);
    padding: 12px 0;
    display: flex;
    justify-content: space-between;
}
.policy-item:last-child {
    border-bottom: none;
}
.status-pill {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 500;
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

</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def api(method: str, path: str, **kwargs):
    try:
        resp = requests.request(method, f"{BACKEND}{path}", timeout=120, **kwargs)
        return resp.json(), None
    except requests.exceptions.ConnectionError:
        return None, "Backend unavailable."
    except Exception as e:
        return None, f"Request error: {type(e).__name__}"

def backend_online() -> bool:
    data, _ = api("GET", "/health")
    return data is not None and data.get("status") == "ok"

def fmt_inr(v: float) -> str:
    return f"₹{v:,.2f}"

# ---------------------------------------------------------------------------
# State initialization
# ---------------------------------------------------------------------------
if "chat_result" not in st.session_state:
    st.session_state.chat_result = None
if "chat_error" not in st.session_state:
    st.session_state.chat_error = None
if "cart_id" not in st.session_state:
    st.session_state.cart_id = ""
if "order_id" not in st.session_state:
    st.session_state.order_id = ""
if "last_request" not in st.session_state:
    st.session_state.last_request = ""

# ---------------------------------------------------------------------------
# Sidebar Navigation
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown('<div class="sidebar-title">MerchantKit</div>', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-subtitle">AI Commerce Agent Gateway</div>', unsafe_allow_html=True)
    
    pages = ["Overview", "AI Buyer", "Commerce", "Guardrails", "Payments", "Audit Trail"]
    
    # Using radio for navigation to avoid page reloads
    page = st.radio("Navigation", pages, label_visibility="collapsed")

# ---------------------------------------------------------------------------
# Header
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
    st.error("FastAPI backend is not reachable. Start it with `python run.py`")
    st.stop()


# ---------------------------------------------------------------------------
# PAGE: OVERVIEW
# ---------------------------------------------------------------------------
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
        
    st.markdown("<br><h4 style='font-size: 16px;'>Recent Activity</h4>", unsafe_allow_html=True)
    
    data, err = api("GET", "/dashboard/audit?limit=5")
    if data and data.get("success") and data["data"]:
        entries = data["data"]
        rows = []
        for e in entries:
            ts = e.get("timestamp", "")
            if len(ts) > 19: ts = ts[11:19]
            status = "Success" if e.get("success") else e.get("error_code", "Failed")
            rows.append({
                "Time": ts,
                "Actor": e.get("actor", ""),
                "Action": e.get("action", ""),
                "Status": status
            })
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    else:
        st.caption("No recent activity.")


# ---------------------------------------------------------------------------
# PAGE: AI BUYER
# ---------------------------------------------------------------------------
elif page == "AI Buyer":
    col_chat, col_exec = st.columns([6, 4], gap="large")
    
    with col_chat:
        user_input = st.text_area("Request", placeholder="Find a gaming mouse under ₹1500 and add the best option to my cart.", height=100, label_visibility="collapsed")
        
        st.markdown('<div class="btn-primary">', unsafe_allow_html=True)
        submit = st.button("Send Request →")
        st.markdown('</div>', unsafe_allow_html=True)
        
        if submit and user_input.strip():
            st.session_state.chat_result = None
            st.session_state.chat_error = None
            with st.spinner("Agent is working..."):
                data, err = api("POST", "/agent/chat", json={"message": user_input.strip()})
            if err:
                st.session_state.chat_error = err
            else:
                st.session_state.chat_result = data
                st.session_state.last_request = user_input.strip()

        if st.session_state.chat_error:
            st.error(st.session_state.chat_error)
            
        if st.session_state.chat_result:
            res = st.session_state.chat_result
            req = st.session_state.get("last_request", "")
            
            st.markdown('<div class="conversation-block">', unsafe_allow_html=True)
            
            if req:
                st.markdown(f"""
                <div class="msg-you">
                    <div class="msg-you-label">You</div>
                    <div class="msg-you-text">{req}</div>
                </div>
                """, unsafe_allow_html=True)
                
            st.markdown(f"""
            <div class="msg-agent">
                <div class="msg-agent-label">Agent</div>
                <div class="msg-agent-text">{res.get("message", "")}</div>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown('</div>', unsafe_allow_html=True)

    with col_exec:
        st.markdown('<div style="font-size: 11px; font-weight: 600; color: #64748b; margin-bottom: 16px; text-transform: uppercase;">Agent Execution</div>', unsafe_allow_html=True)
        
        if st.session_state.chat_result:
            log = st.session_state.chat_result.get("tool_call_log", [])
            if log:
                tl_html = '<div class="timeline">'
                for i, entry in enumerate(log):
                    tool = entry.get("tool_name", "unknown")
                    ok = entry.get("success", False)
                    err_val = entry.get("error")
                    is_rejected = isinstance(err_val, dict) and err_val.get("code") == "GUARDRAIL_VIOLATION"
                    
                    status_class = "success" if ok else ("rejected" if is_rejected else "failed")
                    status_text = "Completed" if ok else ("Rejected" if is_rejected else "Failed")
                    
                    tl_html += f"""
                    <div class="tl-item">
                        <div class="tl-step">{i+1:02d}</div>
                        <div class="tl-content">
                            <div class="tl-title">{tool}</div>
                            <div class="tl-status {status_class}">{status_text}</div>
                        </div>
                    </div>
                    """
                tl_html += '</div>'
                st.markdown(tl_html, unsafe_allow_html=True)
            else:
                st.caption("No tools executed.")
        else:
            st.caption("Execution steps will appear here.")


# ---------------------------------------------------------------------------
# PAGE: COMMERCE
# ---------------------------------------------------------------------------
elif page == "Commerce":
    c1, c2 = st.columns(2)
    with c1:
        st.session_state.cart_id = st.text_input("Cart ID", value=st.session_state.cart_id)
    with c2:
        st.session_state.order_id = st.text_input("Order ID", value=st.session_state.order_id)
        
    st.markdown("<hr style='margin: 24px 0; border: none; border-top: 1px solid var(--border);'>", unsafe_allow_html=True)
    
    if st.session_state.cart_id.strip():
        st.markdown("<h4 style='font-size: 16px;'>Current Cart</h4>", unsafe_allow_html=True)
        data, err = api("GET", f"/dashboard/cart/{st.session_state.cart_id.strip()}")
        if err or not data.get("success"):
            st.caption("Cart not found.")
        else:
            cart = data["data"]
            items = cart.get("items", [])
            if items:
                rows = [{"Product": it["product_id"], "Quantity": it["quantity"], "Price": fmt_inr(it["unit_price"]), "Subtotal": fmt_inr(it["quantity"] * it["unit_price"])} for it in items]
                st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
                subtotal = sum(it["quantity"] * it["unit_price"] for it in items)
                st.markdown(f"<div style='margin-top: 12px; font-size: 14px; color: var(--text-secondary);'>Authoritative Total: <span style='color: var(--text-primary); font-weight: 600;'>{fmt_inr(subtotal)}</span></div>", unsafe_allow_html=True)
            else:
                st.caption("Cart is empty.")
                
    st.markdown("<hr style='margin: 24px 0; border: none; border-top: 1px solid var(--border);'>", unsafe_allow_html=True)
    
    if st.session_state.order_id.strip():
        st.markdown("<h4 style='font-size: 16px;'>Order Details</h4>", unsafe_allow_html=True)
        data, err = api("GET", f"/dashboard/order/{st.session_state.order_id.strip()}")
        if err or not data.get("success"):
            st.caption("Order not found.")
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
            
            st.markdown("<br>", unsafe_allow_html=True)
            items = order.get("items", [])
            if items:
                rows = [{"Product": it["product_name"], "Quantity": it["quantity"], "Price": fmt_inr(it["unit_price"])} for it in items]
                st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


# ---------------------------------------------------------------------------
# PAGE: GUARDRAILS
# ---------------------------------------------------------------------------
elif page == "Guardrails":
    col1, col2 = st.columns(2, gap="large")
    
    with col1:
        st.markdown("<h4 style='font-size: 16px;'>Active Policies</h4>", unsafe_allow_html=True)
        data, err = api("GET", "/dashboard/guardrails")
        if data and data.get("success"):
            p = data["data"]
            cats = ", ".join(c.title() for c in p.get("allowed_categories", []))
            st.markdown(f"""
            <div style="border: 1px solid var(--border); border-radius: 6px; padding: 0 16px;">
                <div class="policy-item">
                    <span style="font-size: 13px; color: var(--text-secondary);">Maximum Order Value</span>
                    <span style="font-size: 14px; font-weight: 500;">{fmt_inr(p['max_order_value'])}</span>
                </div>
                <div class="policy-item">
                    <span style="font-size: 13px; color: var(--text-secondary);">Maximum Items</span>
                    <span style="font-size: 14px; font-weight: 500;">{p['max_item_quantity']}</span>
                </div>
                <div class="policy-item">
                    <span style="font-size: 13px; color: var(--text-secondary);">Allowed Categories</span>
                    <span style="font-size: 14px; font-weight: 500;">{cats}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
    with col2:
        st.markdown("<h4 style='font-size: 16px;'>Latest Decision</h4>", unsafe_allow_html=True)
        audit_data, _ = api("GET", "/dashboard/audit?limit=50")
        latest = None
        if audit_data and audit_data.get("success"):
            for e in audit_data["data"]:
                if e.get("policy_decision") in ("APPROVED", "REJECTED"):
                    latest = e
                    break
        
        if latest:
            dec = latest.get("policy_decision")
            status_cls = "success" if dec == "APPROVED" else "error"
            st.markdown(f"""
            <div style="border: 1px solid var(--border); border-radius: 6px; padding: 16px;">
                <div style="margin-bottom: 8px;">
                    <span class="status-pill {status_cls}">{dec}</span>
                </div>
                <div style="font-size: 14px; color: var(--text-primary); margin-bottom: 4px;">{latest.get("reason") or "Action allowed."}</div>
                <div style="font-size: 12px; color: var(--text-secondary); font-family: monospace;">Action: {latest.get("action")}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.caption("No recent decisions.")


# ---------------------------------------------------------------------------
# PAGE: PAYMENTS
# ---------------------------------------------------------------------------
elif page == "Payments":
    st.session_state.order_id = st.text_input("Order ID", value=st.session_state.order_id)
    
    if st.session_state.order_id.strip():
        order_data = None
        resp, _ = api("GET", f"/dashboard/order/{st.session_state.order_id.strip()}")
        if resp and resp.get("success"):
            order_data = resp["data"]
            
        if order_data:
            pstatus = order_data.get("payment_status") or "NOT_CREATED"
            st.markdown(f"""
            <div style="border: 1px solid var(--border); border-radius: 6px; padding: 24px; margin-top: 16px;">
                <div style="font-size: 12px; color: var(--text-secondary); text-transform: uppercase; font-weight: 600; margin-bottom: 8px;">Payment Status</div>
                <div style="font-size: 24px; font-weight: 600; margin-bottom: 16px;">{pstatus}</div>
                
                <div style="font-size: 13px; color: var(--text-secondary); margin-bottom: 24px;">
                    Provider: Razorpay (Test Mode) <br>
                    Order ID: <code>{order_data.get("razorpay_order_id") or "—"}</code>
                </div>
            """, unsafe_allow_html=True)
            
            if pstatus == "PENDING":
                st.markdown('<div class="btn-primary" style="display: inline-block;">', unsafe_allow_html=True)
                if st.button("Initiate Payment"):
                    res, err = api("POST", "/payment/initiate", json={"order_id": st.session_state.order_id.strip()})
                    if res and res.get("payment_status"):
                        st.success("Payment initiated successfully.")
                        st.rerun()
                    else:
                        st.error("Failed to initiate payment.")
                st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.caption("Order not found.")
    else:
        st.caption("Enter an Order ID to view payment status.")


# ---------------------------------------------------------------------------
# PAGE: AUDIT TRAIL
# ---------------------------------------------------------------------------
elif page == "Audit Trail":
    data, err = api("GET", "/dashboard/audit?limit=100")
    if data and data.get("success") and data["data"]:
        entries = data["data"]
        rows = []
        for e in entries:
            ts = e.get("timestamp", "")
            if len(ts) > 19: ts = ts[11:19]
            
            dec = e.get("policy_decision")
            if dec not in ("APPROVED", "REJECTED"): dec = "—"
            
            status = "SUCCESS" if e.get("success") else e.get("error_code", "FAILED")
            
            rows.append({
                "Time": ts,
                "Actor": e.get("actor", ""),
                "Action": e.get("action", ""),
                "Decision": dec,
                "Status": status,
            })
        
        df = pd.DataFrame(rows)
        
        def color_status(val):
            if val == "SUCCESS": return "color: #16a34a; font-weight: 500;"
            if val in ("FAILED", "GUARDRAIL_VIOLATION", "INVALID_SIGNATURE"): return "color: #dc2626; font-weight: 500;"
            return "color: var(--text-secondary);"
            
        st.dataframe(df.style.map(color_status, subset=["Status"]), hide_index=True, use_container_width=True)
    else:
        st.caption("No audit entries available.")
