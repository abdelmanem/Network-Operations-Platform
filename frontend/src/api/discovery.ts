import type {
  DiscoveryJobRequest,
  DiscoveryJobSubmissionResponse,
  DiscoveryRunListResponse,
} from '../types/api'
import { api, normalizeApiError } from './client'

export async function getDiscoveryRuns(): Promise<DiscoveryRunListResponse> {
  try {
    const response = await api.get<DiscoveryRunListResponse>(
      '/api/v1/history/discovery-runs',
    )
    return response.data
  } catch (error) {
    throw new Error(normalizeApiError(error))
  }
}

export async function submitDiscoveryJob(
  payload: DiscoveryJobRequest,
): Promise<DiscoveryJobSubmissionResponse> {
  try {
    const response = await api.post<DiscoveryJobSubmissionResponse>(
      '/api/v1/jobs/discovery',
      payload,
    )
    return response.data
  } catch (error) {
    throw new Error(normalizeApiError(error))
  }
}
