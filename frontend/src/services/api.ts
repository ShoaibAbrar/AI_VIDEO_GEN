import axios from 'axios'

const API_BASE_URL = (import.meta as ImportMeta & { env?: { VITE_API_URL?: string } }).env?.VITE_API_URL || 'http://localhost:8000/api/v1'

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

export const healthApi = {
  check: () => apiClient.get('/health'),
}

export default apiClient
