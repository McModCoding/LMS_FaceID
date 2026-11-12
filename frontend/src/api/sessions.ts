import api from './client'
import { Session, SessionUpdateDTO } from '../types/session'

export const sessionsApi = {
  update: async (sessionId: number, data: SessionUpdateDTO): Promise<Session> => {
    const res = await api.patch<Session>(`/sessions/${sessionId}`, data)
    return res.data
  },

  cancel: async (sessionId: number): Promise<Session> => {
    const res = await api.post<Session>(`/sessions/${sessionId}/cancel`)
    return res.data
  },

  open: async (sessionId: number, reason?: string): Promise<Session> => {
    const res = await api.post<Session>(`/sessions/${sessionId}/open`, reason ? { reason } : undefined)
    return res.data
  },

  close: async (sessionId: number): Promise<Session> => {
    const res = await api.post<Session>(`/sessions/${sessionId}/close`)
    return res.data
  },
}
