import { request } from './client';
import type { ApiResult, GuardrailPolicy, AuditEntry, ToolDefinition } from './types';

/**
 * Fetch the active guardrail policy configuration.
 */
export async function getGuardrailPolicy(): Promise<ApiResult<GuardrailPolicy>> {
  return request<ApiResult<GuardrailPolicy>>('/dashboard/guardrails');
}

/**
 * Fetch recent audit trail entries including policy decisions and details.
 */
export async function getAuditTrail(limit = 50): Promise<ApiResult<AuditEntry[]>> {
  return request<ApiResult<AuditEntry[]>>(`/dashboard/audit?limit=${limit}`);
}

/**
 * Fetch registered allowed tools from the backend gateway.
 */
export async function getAllowedTools(): Promise<ApiResult<ToolDefinition[]>> {
  return request<ApiResult<ToolDefinition[]>>('/dashboard/tools');
}
