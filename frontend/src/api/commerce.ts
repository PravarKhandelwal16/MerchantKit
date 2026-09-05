import { request } from './client';
import type { ApiResult, Product, Cart, Order } from './types';

/**
 * Fetch all products in the catalog.
 */
export async function getProducts(): Promise<ApiResult<Product[]>> {
  return request<ApiResult<Product[]>>('/dashboard/products');
}

/**
 * Fetch recent carts.
 */
export async function getCarts(limit = 50): Promise<ApiResult<Cart[]>> {
  return request<ApiResult<Cart[]>>(`/dashboard/carts?limit=${limit}`);
}

/**
 * Fetch recent orders.
 */
export async function getOrders(limit = 50): Promise<ApiResult<Order[]>> {
  return request<ApiResult<Order[]>>(`/dashboard/orders?limit=${limit}`);
}

/**
 * Fetch a single cart by ID.
 */
export async function getCart(cartId: string): Promise<ApiResult<Cart>> {
  return request<ApiResult<Cart>>(`/dashboard/cart/${encodeURIComponent(cartId)}`);
}

/**
 * Fetch a single order by ID.
 */
export async function getOrder(orderId: string): Promise<ApiResult<Order>> {
  return request<ApiResult<Order>>(`/dashboard/order/${encodeURIComponent(orderId)}`);
}
