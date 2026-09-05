// MerchantKit API types — mirrors FastAPI response shapes.
// All commerce/payment types are read-only from the frontend's perspective.

export interface ApiResult<T> {
  success: boolean;
  data?: T;
  error?: string;
}

export interface HealthResponse {
  status: string;
}

export interface LLMHealthResponse {
  provider: string;
  model: string;
  status: string;
  configured?: boolean;
  error?: string | null;
}

// --- Agent ---

export interface ToolCallSummary {
  tool_name: string;
  success: boolean;
  error?: string | Record<string, unknown> | null;
}

export interface SessionData {
  cart_id: string | null;
  order_id: string | null;
}

export interface AgentChatResponse {
  success: boolean;
  message: string;
  stop_reason: string;
  tool_calls_made: number;
  tool_call_log: ToolCallSummary[];
  session_data: SessionData;
}

// --- Commerce ---

export interface Product {
  product_id: string;
  name: string;
  description: string;
  price: number;
  category: string;
  stock: number;
  image_url?: string | null;
}

export interface CartItem {
  product_id: string;
  product_name?: string | null;
  quantity: number;
  unit_price: number;
}

export interface Cart {
  cart_id: string;
  status: string;
  created_at: string;
  updated_at: string;
  items: CartItem[];
  subtotal: number;
  total_quantity: number;
}

export interface OrderItem {
  order_id: string;
  product_id: string;
  product_name: string;
  quantity: number;
  unit_price: number;
}

export interface Order {
  order_id: string;
  cart_id: string;
  total_amount: number;
  currency: string;
  status: string;
  created_at: string;
  payment_provider: string | null;
  razorpay_order_id: string | null;
  payment_status: string | null;
  items: OrderItem[];
}

// --- Guardrails ---

export interface GuardrailPolicy {
  max_order_value: number;
  max_item_quantity: number;
  allowed_categories: string[];
  require_payment_confirmation: boolean;
}

export interface ToolDefinition {
  name: string;
  description: string;
}

// --- Audit ---

export interface AuditEntry {
  id: number;
  timestamp: string;
  actor: string;
  action: string;
  policy_decision: string;
  reason: string | null;
  success: boolean;
  error_code: string | null;
  arguments?: Record<string, unknown> | null;
  result?: Record<string, unknown> | null;
}

// --- Session ---

export interface SessionInfo {
  cart_id: string | null;
  order_id: string | null;
}

// --- Payment ---

export interface PaymentInitiateResponse {
  success: boolean;
  order_id?: string;
  razorpay_order_id?: string;
  amount?: number;
  currency?: string;
  payment_status?: string;
  error?: string;
}
