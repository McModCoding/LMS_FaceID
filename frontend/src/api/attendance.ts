import api from './client'
import { AttendanceStatus, SessionAttendanceResponse } from '../types/attendance'

export const attendanceApi = {
  getSession: async (sessionId: number): Promise<SessionAttendanceResponse> => {
    const response = await api.get<SessionAttendanceResponse>(`/sessions/${sessionId}/attendance`)
    return response.data
  },
  checkIn: async (sessionId: number, studentId: number) => {
    const response = await api.post(`/sessions/${sessionId}/attendance/${studentId}/check-in`)
    return response.data
  },
  update: async (sessionId: number, studentId: number, data: { status: AttendanceStatus; note?: string; expected_status?: AttendanceStatus }) => {
    const response = await api.patch(`/sessions/${sessionId}/attendance/${studentId}`, data)
    return response.data
  },
  exportSession: async (sessionId: number): Promise<Blob> => {
    const response = await api.get(`/sessions/${sessionId}/attendance/export`, { responseType: 'blob' })
    return response.data
  },
}
