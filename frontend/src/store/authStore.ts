import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import apiClient from '@/services/api'

export interface User {
  id: number
  username: string
  email: string
  first_name?: string
  last_name?: string
  is_active: boolean
  roles: Array<{ id: number; name: string }>
}

export interface AuthState {
  user: User | null
  accessToken: string | null
  refreshToken: string | null
  isLoading: boolean
  error: string | null

  // Actions
  setUser: (user: User | null) => void
  setTokens: (accessToken: string, refreshToken: string) => void
  login: (username: string, password: string) => Promise<void>
  register: (username: string, email: string, password: string, firstName?: string, lastName?: string) => Promise<void>
  logout: () => void
  refreshAccessToken: () => Promise<void>
  setError: (error: string | null) => void
  isAdmin: () => boolean
  isManager: () => boolean
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      isLoading: false,
      error: null,

      setUser: (user) => set({ user }),
      setTokens: (accessToken, refreshToken) => set({ accessToken, refreshToken }),

      login: async (username: string, password: string) => {
        set({ isLoading: true, error: null })
        try {
          const response = await apiClient.post('/auth/login', {
            username,
            password,
          })

          const { access_token, refresh_token } = response.data

          // Store tokens
          set({
            accessToken: access_token,
            refreshToken: refresh_token,
          })

          // Fetch current user
          const userResponse = await apiClient.get('/auth/me')
          set({ user: userResponse.data, error: null })
        } catch (error: any) {
          const errorMessage = error.response?.data?.detail || 'Login failed'
          set({ error: errorMessage })
          throw new Error(errorMessage)
        } finally {
          set({ isLoading: false })
        }
      },

      register: async (username: string, email: string, password: string, firstName?: string, lastName?: string) => {
        set({ isLoading: true, error: null })
        try {
          const response = await apiClient.post('/auth/register', {
            username,
            email,
            password,
            first_name: firstName,
            last_name: lastName,
          })

          set({ user: response.data, error: null })
        } catch (error: any) {
          const errorMessage = error.response?.data?.detail || 'Registration failed'
          set({ error: errorMessage })
          throw new Error(errorMessage)
        } finally {
          set({ isLoading: false })
        }
      },

      logout: () => {
        set({
          user: null,
          accessToken: null,
          refreshToken: null,
          error: null,
        })
      },

      refreshAccessToken: async () => {
        const { refreshToken } = get()
        if (!refreshToken) {
          set({ error: 'No refresh token available' })
          throw new Error('No refresh token available')
        }

        try {
          const response = await apiClient.post('/auth/refresh', {
            refresh_token: refreshToken,
          })

          set({ accessToken: response.data.access_token, error: null })
        } catch (error: any) {
          const errorMessage = error.response?.data?.detail || 'Token refresh failed'
          set({ error: errorMessage })
          // Clear tokens and user on refresh failure
          set({
            accessToken: null,
            refreshToken: null,
            user: null,
          })
          throw new Error(errorMessage)
        }
      },

      setError: (error) => set({ error }),

      isAdmin: () => {
        const { user } = get()
        return user?.roles?.some((role) => role.name === 'admin') || false
      },

      isManager: () => {
        const { user } = get()
        return user?.roles?.some((role) => role.name === 'manager') || false
      },
    }),
    {
      name: 'auth-store',
      partialize: (state) => ({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        user: state.user,
      }),
    }
  )
)
