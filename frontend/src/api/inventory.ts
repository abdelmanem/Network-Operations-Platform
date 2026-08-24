import type { InventoryListResponse } from '../types/api'
import { api, normalizeApiError } from './client'

export interface InventoryQuery {
  search?: string
  manufacturer?: string
  platform?: string
  sort_by?: 'name' | 'model' | 'serial_number' | 'platform' | 'management_ip'
  sort_direction?: 'asc' | 'desc'
}

export async function listNetboxInventory(
  page: number = 1,
  pageSize: number = 50,
  query: InventoryQuery = {},
): Promise<InventoryListResponse> {
  try {
    const response = await api.get<InventoryListResponse>(
      '/api/v1/inventory/netbox',
      { params: { page, page_size: pageSize, ...query } },
    )
    return response.data
  } catch (error) {
    throw new Error(normalizeApiError(error))
  }
}

export async function listLiveInventory(
  page: number = 1,
  pageSize: number = 50,
  query: InventoryQuery = {},
): Promise<InventoryListResponse> {
  try {
    const response = await api.get<InventoryListResponse>(
      '/api/v1/inventory/live',
      { params: { page, page_size: pageSize, ...query } },
    )
    return response.data
  } catch (error) {
    throw new Error(normalizeApiError(error))
  }
}
