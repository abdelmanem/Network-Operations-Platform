import type { DeviceComparisonResponse } from '../types/api'
import { api, normalizeApiError } from './client'

export async function compareDevice(
  deviceId: string,
  runId?: string,
): Promise<DeviceComparisonResponse> {
  try {
    const params = runId ? { run_id: runId } : undefined
    const response = await api.get<DeviceComparisonResponse>(
      `/api/v1/devices/${deviceId}/compare`,
      { params },
    )
    return response.data
  } catch (error) {
    throw new Error(normalizeApiError(error))
  }
}
