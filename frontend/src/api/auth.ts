/**
 * Auth API - Authentication endpoints
 */
import { api, ApiResponse } from './client'
import { User, AuthTokens } from '@/store/authStore'

export interface LoginRequest {
  email: string
  password: string
}

export interface RegisterRequest {
  email: string
  password: string
  full_name: string
  organization_name: string
}

export interface AuthResponse {
  tokens: AuthTokens
  user: User
}

export interface ChangePasswordRequest {
  current_password: string
  new_password: string
}

// Auth requests get longer timeout due to password hashing
const AUTH_TIMEOUT = 90_000

export const authApi = {
  login: (data: LoginRequest): Promise<ApiResponse<AuthResponse>> =>
    api.post<AuthResponse>('/api/auth/login', data, { timeout: AUTH_TIMEOUT }),

  register: (data: RegisterRequest): Promise<ApiResponse<AuthResponse>> =>
    api.post<AuthResponse>('/api/auth/register', data, { timeout: AUTH_TIMEOUT }),

  logout: (token: string): Promise<ApiResponse<{ message: string }>> =>
    api.post<{ message: string }>('/api/auth/logout', undefined, {
      headers: { Authorization: `Bearer ${token}` },
    }),

  me: (token: string): Promise<ApiResponse<User>> =>
    api.get<User>('/api/auth/me', {
      headers: { Authorization: `Bearer ${token}` },
    }),

  changePassword: (
    data: ChangePasswordRequest,
    token: string
  ): Promise<ApiResponse<{ message: string }>> =>
    api.post<{ message: string }>('/api/auth/change-password', data, {
      headers: { Authorization: `Bearer ${token}` },
    }),

  refresh: (refreshToken: string): Promise<ApiResponse<AuthTokens>> =>
    api.post<AuthTokens>('/api/auth/refresh', { refresh_token: refreshToken }),
}
