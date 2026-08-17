import { api } from './client'
import type {
  NetBoxIntegrationStatusResponse,
  NetBoxTestConnectionResponse,
  NetBoxSyncResponse,
} from '../types/api'

export async function getNetBoxStatus(): Promise<NetBoxIntegrationStatusResponse> {
  const response = await api.get<NetBoxIntegrationStatusResponse>(
    '/api/v1/integrations/netbox/status',
  )
  return response.data
}

export async function testNetBoxConnection(): Promise<NetBoxTestConnectionResponse> {
  const response = await api.post<NetBoxTestConnectionResponse>(
    '/api/v1/integrations/netbox/test',
  )
  return response.data
}

export async function syncNetBoxInventory(): Promise<NetBoxSyncResponse> {
  const response = await api.post<NetBoxSyncResponse>(
    '/api/v1/integrations/netbox/sync',
  )
  return response.data
}
