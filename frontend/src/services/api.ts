import type {
  LoginRequest,
  TokenResponse,
  UserResponse,
} from '../types/api'
import { api, normalizeApiError } from '../api/client'
import { getDashboardKpis, getDashboardTrends } from '../api/dashboard'

export async function login(credentials: LoginRequest): Promise<TokenResponse> {
  try {
    const response = await api.post<TokenResponse>('/auth/login', credentials)
    return response.data
  } catch (error) {
    throw new Error(normalizeApiError(error))
  }
}

export async function getCurrentUser(): Promise<UserResponse> {
  try {
    const response = await api.get<UserResponse>('/auth/me')
    return response.data
  } catch (error) {
    throw new Error(normalizeApiError(error))
  }
}

export { getDashboardKpis, getDashboardTrends }

export default api
