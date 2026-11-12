import api from './client'

export interface ToggleStatusPayload {
  is_active: boolean
}

export const usersApi = {
  toggleStatus: async (userId: number, isActive: boolean): Promise<{ message: string; is_active: boolean }> => {
    const response = await api.patch(`/users/${userId}/status`, { is_active: isActive })
    return response.data
  },

  resetPassword: async (userId: number): Promise<{ temp_password: string }> => {
    const response = await api.post(`/users/${userId}/reset-password`)
    return response.data
  },
}
