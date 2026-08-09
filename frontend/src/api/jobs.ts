import type { JobListResponse, JobStatusResponse } from '../types/api'
import { api, normalizeApiError } from './client'

export async function getJobs(): Promise<JobListResponse> {
  try {
    const response = await api.get<JobListResponse>('/api/v1/jobs')
    return response.data
  } catch (error) {
    throw new Error(normalizeApiError(error))
  }
}

export async function getJob(jobId: string): Promise<JobStatusResponse> {
  try {
    const response = await api.get<JobStatusResponse>(`/api/v1/jobs/${jobId}`)
    return response.data
  } catch (error) {
    throw new Error(normalizeApiError(error))
  }
}

export async function cancelJob(jobId: string): Promise<{ status: string; job_id: string }> {
  try {
    const response = await api.delete<{ status: string; job_id: string }>(
      `/api/v1/jobs/${jobId}`,
    )
    return response.data
  } catch (error) {
    throw new Error(normalizeApiError(error))
  }
}
