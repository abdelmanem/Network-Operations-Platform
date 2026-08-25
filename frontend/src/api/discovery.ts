import type {
  CredentialProfileRequest,
  CredentialProfileResponse,
  CredentialProfileTestRequest,
  CredentialProfileTestResponse,
  DiscoveryApiJobRequest,
  DiscoveryApiJobResponse,
  DiscoveryJobQueryParams,
  DiscoveryJobListResponse,
  DiscoveryEvidenceResponse,
  DiscoveryDeviceResultResponse,
  DiscoveryJobRequest,
  DiscoveryJobSubmissionResponse,
  DiscoveryRunListResponse,
  DiscoveryTargetRequest,
  DiscoveryTargetResponse,
  DiscoveryTargetUpdateRequest,
} from '../types/api'
import { api, normalizeApiError } from './client'

export function discoveryJobsErrorTitle(error: string | null): string {
  const normalized = error?.toLowerCase() ?? ''
  if (normalized.includes('authentication') || normalized.includes('sign in')) {
    return 'Sign in required.'
  }
  if (normalized.includes('permission') || normalized.includes('forbidden')) {
    return 'Permission required.'
  }
  return 'Unable to load discovery jobs.'
}

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

export async function listDiscoveryTargets(): Promise<
  DiscoveryTargetResponse[]
> {
  try {
    const response = await api.get<DiscoveryTargetResponse[]>(
      '/api/v1/discovery/targets',
    )
    return response.data
  } catch (error) {
    throw new Error(normalizeApiError(error))
  }
}

export async function createDiscoveryTarget(
  payload: DiscoveryTargetRequest,
): Promise<DiscoveryTargetResponse> {
  try {
    const response = await api.post<DiscoveryTargetResponse>(
      '/api/v1/discovery/targets',
      payload,
    )
    return response.data
  } catch (error) {
    throw new Error(normalizeApiError(error))
  }
}

export async function updateDiscoveryTarget(
  targetId: string,
  payload: DiscoveryTargetUpdateRequest,
): Promise<DiscoveryTargetResponse> {
  try {
    const response = await api.patch<DiscoveryTargetResponse>(
      `/api/v1/discovery/targets/${targetId}`,
      payload,
    )
    return response.data
  } catch (error) {
    throw new Error(normalizeApiError(error))
  }
}


export async function listDiscoveryCredentialProfiles(): Promise<
  CredentialProfileResponse[]
> {
  try {
    const response = await api.get<CredentialProfileResponse[]>(
      '/api/v1/credentials/profiles',
    )
    return response.data
  } catch (error) {
    throw new Error(normalizeApiError(error))
  }
}

export async function createDiscoveryCredentialProfile(
  payload: CredentialProfileRequest,
): Promise<CredentialProfileResponse> {
  try {
    const response = await api.post<CredentialProfileResponse>(
      '/api/v1/credentials/profiles',
      payload,
    )
    return response.data
  } catch (error) {
    throw new Error(normalizeApiError(error))
  }
}

export async function testDiscoveryCredentialProfile(
  profileId: string,
  payload: CredentialProfileTestRequest,
): Promise<CredentialProfileTestResponse> {
  try {
    const response = await api.post<CredentialProfileTestResponse>(
      `/api/v1/credentials/profiles/${profileId}/test`,
      payload,
    )
    return response.data
  } catch (error) {
    throw new Error(normalizeApiError(error))
  }
}

export async function createDiscoveryApiJob(
  payload: DiscoveryApiJobRequest,
): Promise<DiscoveryApiJobResponse> {
  try {
    const response = await api.post<DiscoveryApiJobResponse>(
      '/api/v1/discovery/jobs',
      payload,
    )
    return response.data
  } catch (error) {
    throw new Error(normalizeApiError(error))
  }
}

export async function listDiscoveryApiJobs(
  paramsOrPage: number | DiscoveryJobQueryParams = 1,
  pageSize = 25,
): Promise<DiscoveryJobListResponse> {
  const params =
    typeof paramsOrPage === 'number'
      ? { page: paramsOrPage, page_size: pageSize }
      : { page: 1, page_size: 25, ...paramsOrPage }
  try {
    const response = await api.get<DiscoveryJobListResponse>(
      '/api/v1/discovery/jobs',
      { params },
    )
    return response.data
  } catch (error) {
    throw new Error(normalizeApiError(error))
  }
}

export async function cancelDiscoveryApiJob(
  jobId: string,
  reason = 'Cancelled by operator',
): Promise<DiscoveryApiJobResponse> {
  try {
    const response = await api.post<DiscoveryApiJobResponse>(
      `/api/v1/discovery/jobs/${jobId}/cancel`,
      { reason },
    )
    return response.data
  } catch (error) {
    throw new Error(normalizeApiError(error))
  }
}

export async function resolveDiscoveryApiJobCancellation(
  jobId: string,
): Promise<DiscoveryApiJobResponse> {
  try {
    const response = await api.post<DiscoveryApiJobResponse>(
      `/api/v1/discovery/jobs/${jobId}/cancel/force`,
    )
    return response.data
  } catch (error) {
    throw new Error(normalizeApiError(error))
  }
}

export async function getDiscoveryApiJob(
  jobId: string,
): Promise<DiscoveryApiJobResponse> {
  try {
    const response = await api.get<DiscoveryApiJobResponse>(
      `/api/v1/discovery/jobs/${jobId}`,
    )
    return response.data
  } catch (error) {
    throw new Error(normalizeApiError(error))
  }
}

export async function getDiscoveryEvidence(
  jobId: string,
): Promise<DiscoveryEvidenceResponse[]> {
  try {
    const response = await api.get<DiscoveryEvidenceResponse[]>(
      `/api/v1/discovery/jobs/${jobId}/evidence`,
    )
    return response.data
  } catch (error) {
    throw new Error(normalizeApiError(error))
  }
}

export async function getDiscoveryDeviceResults(
  jobId: string,
): Promise<DiscoveryDeviceResultResponse[]> {
  try {
    const response = await api.get<DiscoveryDeviceResultResponse[]>(
      `/api/v1/discovery/jobs/${jobId}/devices`,
    )
    return response.data
  } catch (error) {
    throw new Error(normalizeApiError(error))
  }
}
