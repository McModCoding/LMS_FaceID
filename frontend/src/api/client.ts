import axios from 'axios'

export const api = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
})

api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response) {
      const { status } = error.response
      let data = error.response.data
      if (data instanceof Blob && data.type.includes('json')) {
        try {
          data = JSON.parse(await data.text())
          error.response.data = data
        } catch { /* ignore */ }
      }
      const responseData = data as {
        detail?: unknown
        error?: { code?: string; message?: string }
      }
      if (
        !responseData.error &&
        typeof responseData.detail === 'object' &&
        responseData.detail !== null &&
        !Array.isArray(responseData.detail)
      ) {
        responseData.error = responseData.detail as { code?: string; message?: string }
      }
      const errorCode = responseData.error?.code

      if (status === 403 && errorCode === 'PASSWORD_CHANGE_REQUIRED') {
        if (window.location.pathname !== '/change-password') {
          window.location.href = '/change-password'
        }
      } else if (status === 401) {
        if (window.location.pathname !== '/login') {
          localStorage.removeItem('token')
          localStorage.removeItem('user')
          window.location.href = '/login'
        }
      }
    }
    return Promise.reject(error)
  }
)

export default api
