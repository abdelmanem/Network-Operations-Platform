import type {
  DashboardKpiSummaryResponse,
  DashboardTrendsResponseEnvelope,
} from '../types/api'
import { api, normalizeApiError } from './client'

export async function getDashboardKpis(): Promise<DashboardKpiSummaryResponse> {
  try {
    const response = await api.get<DashboardKpiSummaryResponse>(
      '/api/v1/dashboard/kpis',
    )
    return response.data
  } catch (error) {
    throw new Error(normalizeApiError(error))
  }
}

export async function getDashboardAggregates(granularity = 'daily') {
  try {
    const response = await api.get(
      `/api/v1/dashboard/aggregates?granularity=${granularity}`,
    )
    return response.data
  } catch (error) {
    throw new Error(normalizeApiError(error))
  }
}

export async function getDashboardTrends(): Promise<DashboardTrendsResponseEnvelope> {
  try {
    const response = await api.get<DashboardTrendsResponseEnvelope>(
      '/api/v1/dashboard/trends',
    )
    return response.data
  } catch (error) {
    throw new Error(normalizeApiError(error))
  }
}
