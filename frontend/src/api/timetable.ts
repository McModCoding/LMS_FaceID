import api from './client'
import { TimetableResponse } from '../types/timetable'

export interface GetMyTimetableParams {
  from_date?: string // YYYY-MM-DD
  to_date?: string // YYYY-MM-DD
}

export interface GetAdminTimetableParams {
  from_date?: string
  to_date?: string
  lecturer_id?: number
  department_id?: number
  room?: string
  class_id?: number
}

export const timetableApi = {
  getMyTimetable: async (params?: GetMyTimetableParams): Promise<TimetableResponse> => {
    const res = await api.get<TimetableResponse>('/me/timetable', { params })
    return res.data
  },

  getAdminTimetable: async (params?: GetAdminTimetableParams): Promise<TimetableResponse> => {
    const res = await api.get<TimetableResponse>('/admin/timetable', { params })
    return res.data
  },
}
