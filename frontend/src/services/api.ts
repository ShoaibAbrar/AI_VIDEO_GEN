import axios from 'axios'

const API_BASE_URL = (import.meta as ImportMeta & { env?: { VITE_API_URL?: string } }).env?.VITE_API_URL || '/api/v1'

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Add auth token to requests
apiClient.interceptors.request.use((config) => {
  try {
    const persisted = localStorage.getItem('auth-store')
    if (persisted) {
      const parsed = JSON.parse(persisted)
      const token = parsed?.state?.accessToken || localStorage.getItem('access_token')
      if (token) {
        config.headers.Authorization = `Bearer ${token}`
      }
    } else {
      const token = localStorage.getItem('access_token')
      if (token) {
        config.headers.Authorization = `Bearer ${token}`
      }
    }
  } catch {
    // Ignore localStorage read failures
  }

  return config
})

// Global response interceptor for session expiration (401)
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    if (error.response?.status === 401 && !originalRequest._retry && !originalRequest.url?.includes('/auth/login')) {
      originalRequest._retry = true

      try {
        const persisted = localStorage.getItem('auth-store')
        if (persisted) {
          const parsed = JSON.parse(persisted)
          const refreshToken = parsed?.state?.refreshToken

          if (refreshToken) {
            const refreshRes = await axios.post(`${API_BASE_URL}/auth/refresh`, {
              refresh_token: refreshToken,
            })

            const newAccessToken = refreshRes.data.access_token
            parsed.state.accessToken = newAccessToken
            localStorage.setItem('auth-store', JSON.stringify(parsed))

            originalRequest.headers.Authorization = `Bearer ${newAccessToken}`
            return apiClient(originalRequest)
          }
        }
      } catch (refreshErr) {
        localStorage.removeItem('auth-store')
        if (window.location.pathname !== '/login') {
          window.location.href = '/login'
        }
      }
    }

    return Promise.reject(error)
  }
)

export const healthApi = {
  check: () => apiClient.get('/health'),
}

export default apiClient
