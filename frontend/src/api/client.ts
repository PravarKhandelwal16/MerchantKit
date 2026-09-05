import type {
  ApiResult,
  AgentChatResponse,
  GuardrailPolicy,
  AuditEntry,
  SessionInfo,
  PaymentInitiateResponse,
  LLMHealthResponse,
} from './types';

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

// Default timeout for regular requests (ms)
const DEFAULT_TIMEOUT_MS = 10_000;
// Agent chat can take 2+ minutes on local inference
const AGENT_TIMEOUT_MS = 300_000;

class ApiError extends Error {
  constructor(
    message: string,
    public readonly status?: number,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export async function request<T>(
  path: string,
  options: RequestInit = {},
  timeoutMs = DEFAULT_TIMEOUT_MS,
): Promise<T> {
  const controller = new AbortController();
  const timerId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(`${BASE_URL}${path}`, {
      ...options,
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });

    if (!response.ok) {
      throw new ApiError(`HTTP ${response.status}`, response.status);
    }

    return response.json() as Promise<T>;
  } catch (err) {
    if (err instanceof ApiError) throw err;
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new ApiError('Request timed out (local AI model may still be running)');
    }
    if (err instanceof TypeError && err.message.includes('fetch')) {
      throw new ApiError('Cannot connect to MerchantKit backend at ' + BASE_URL);
    }
    throw new ApiError(err instanceof Error ? err.message : 'Unknown error');
  } finally {
    clearTimeout(timerId);
  }
}

// -----------------------------------------------------------------------
// Health
// -----------------------------------------------------------------------

export async function checkHealth(): Promise<boolean> {
  try {
    const data = await request<{ status: string }>('/health', {}, 3_000);
    return data.status === 'ok';
  } catch {
    return false;
  }
}

export async function getLLMHealth(): Promise<LLMHealthResponse | null> {
  try {
    return await request<LLMHealthResponse>('/health/llm', {}, 3_000);
  } catch {
    return null;
  }
}

// -----------------------------------------------------------------------
// Agent
// -----------------------------------------------------------------------

export async function sendAgentMessage(message: string): Promise<AgentChatResponse> {
  return request<AgentChatResponse>(
    '/agent/chat',
    {
      method: 'POST',
      body: JSON.stringify({ message }),
    },
    AGENT_TIMEOUT_MS,
  );
}

// -----------------------------------------------------------------------
// Commerce — read-only (implemented in ./commerce.ts)
// -----------------------------------------------------------------------

export { getProducts, getCarts, getOrders, getCart, getOrder } from './commerce';

// -----------------------------------------------------------------------
// Guardrails — read-only
// -----------------------------------------------------------------------

export async function getGuardrails(): Promise<ApiResult<GuardrailPolicy>> {
  return request<ApiResult<GuardrailPolicy>>('/dashboard/guardrails');
}

// -----------------------------------------------------------------------
// Audit — read-only
// -----------------------------------------------------------------------

export async function getAuditTrail(limit = 100): Promise<ApiResult<AuditEntry[]>> {
  return request<ApiResult<AuditEntry[]>>(`/dashboard/audit?limit=${limit}`);
}

// -----------------------------------------------------------------------
// Session — convenience read
// -----------------------------------------------------------------------

export async function getSession(): Promise<ApiResult<SessionInfo>> {
  return request<ApiResult<SessionInfo>>('/dashboard/session');
}

// -----------------------------------------------------------------------
// Payment
// -----------------------------------------------------------------------

export async function initiatePayment(orderId: string): Promise<PaymentInitiateResponse> {
  return request<PaymentInitiateResponse>(
    '/payment/initiate',
    {
      method: 'POST',
      body: JSON.stringify({ order_id: orderId }),
    },
  );
}

// -----------------------------------------------------------------------
// Tools — execute via gateway
// -----------------------------------------------------------------------

export async function executeTool(
  tool: string,
  args: Record<string, unknown>,
): Promise<ApiResult<unknown>> {
  return request<ApiResult<unknown>>(
    '/tools/execute',
    {
      method: 'POST',
      body: JSON.stringify({ tool, arguments: args }),
    },
  );
}
