import api from './client'
import {
  Class,
  ClassCreateDTO,
  ClassListResponse,
  ClassStatus,
  ClassStudent,
  ClassStudentListResponse,
  ClassUpdateDTO,
  EnrollmentImportPreview,
} from '../types/class'
import { Schedule, ScheduleCreateDTO, ScheduleUpdateDTO } from '../types/schedule'
import { Session, SessionListResponse, SessionMakeupCreateDTO } from '../types/session'

export interface GetClassesParams {
  page?: number
  page_size?: number
  semester_id?: number
  subject_id?: number
  lecturer_id?: number
  department_id?: number
  status?: ClassStatus
  q?: string
}

export const classesApi = {
  getAll: async (params?: GetClassesParams): Promise<ClassListResponse> => {
    const res = await api.get<ClassListResponse>('/classes', { params })
    return res.data
  },

  getById: async (id: number): Promise<Class> => {
    const res = await api.get<Class>(`/classes/${id}`)
    return res.data
  },

  create: async (data: ClassCreateDTO): Promise<Class> => {
    const res = await api.post<Class>('/classes', data)
    return res.data
  },

  update: async (id: number, data: ClassUpdateDTO): Promise<Class> => {
    const res = await api.patch<Class>(`/classes/${id}`, data)
    return res.data
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/classes/${id}`)
  },

  activate: async (id: number): Promise<Class> => {
    const res = await api.post<Class>(`/classes/${id}/activate`)
    return res.data
  },

  close: async (id: number): Promise<Class> => {
    const res = await api.post<Class>(`/classes/${id}/close`)
    return res.data
  },

  // Students in class
  getStudents: async (
    classId: number,
    params?: { page?: number; page_size?: number; q?: string; status?: string }
  ): Promise<ClassStudentListResponse> => {
    const res = await api.get<ClassStudentListResponse>(`/classes/${classId}/students`, { params })
    return res.data
  },

  enrollStudents: async (classId: number, studentIds: number[]): Promise<ClassStudent[]> => {
    const res = await api.post<ClassStudent[]>(`/classes/${classId}/students`, {
      student_ids: studentIds,
    })
    return res.data
  },

  dropStudent: async (classId: number, studentId: number): Promise<void> => {
    await api.delete(`/classes/${classId}/students/${studentId}`)
  },

  importPreview: async (classId: number, file: File): Promise<EnrollmentImportPreview> => {
    const formData = new FormData()
    formData.append('file', file)
    const res = await api.post<EnrollmentImportPreview>(
      `/classes/${classId}/students/import/preview`,
      formData,
      {
        headers: { 'Content-Type': 'multipart/form-data' },
      }
    )
    return res.data
  },

  importConfirm: async (classId: number, validRows: any[]): Promise<any> => {
    const res = await api.post(`/classes/${classId}/students/import/confirm`, {
      valid_rows: validRows,
    })
    return res.data
  },

  // Schedules in class
  getSchedules: async (classId: number): Promise<Schedule[]> => {
    const res = await api.get<Schedule[]>(`/classes/${classId}/schedules`)
    return res.data
  },

  createSchedule: async (classId: number, data: ScheduleCreateDTO): Promise<Schedule> => {
    const res = await api.post<Schedule>(`/classes/${classId}/schedules`, data)
    return res.data
  },

  updateSchedule: async (classId: number, scheduleId: number, data: ScheduleUpdateDTO): Promise<Schedule> => {
    const res = await api.patch<Schedule>(`/classes/${classId}/schedules/${scheduleId}`, data)
    return res.data
  },

  deleteSchedule: async (classId: number, scheduleId: number): Promise<void> => {
    await api.delete(`/classes/${classId}/schedules/${scheduleId}`)
  },

  // Sessions in class
  getSessions: async (
    classId: number,
    params?: { page?: number; page_size?: number; status?: string }
  ): Promise<SessionListResponse> => {
    const res = await api.get<SessionListResponse>(`/classes/${classId}/sessions`, { params })
    return res.data
  },

  createMakeupSession: async (classId: number, data: SessionMakeupCreateDTO): Promise<Session> => {
    const res = await api.post<Session>(`/classes/${classId}/sessions`, data)
    return res.data
  },
}
