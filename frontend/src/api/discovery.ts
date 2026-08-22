import type {
  CredentialProfileRequest,
  CredentialProfileResponse,
  CredentialProfileTestRequest,
  CredentialProfileTestResponse,
  DiscoveryApiJobRequest,
  DiscoveryApiJobResponse,
  DiscoveryEvidenceResponse,
  DiscoveryDeviceResultResponse,
  DiscoveryJobRequest,
  DiscoveryJobSubmissionResponse,
  DiscoveryRunListResponse,
  DiscoveryTargetRequest,
  DiscoveryTargetResponse,
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
