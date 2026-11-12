import api from './client'
import {
  Lecturer,
  LecturerType,
  CreateLecturerDTO,
  UpdateLecturerDTO,
  LecturerCreateResponse,
} from '../types/lecturer'

export interface LecturersQueryParams {
  page?: number
  page_size?: number
  q?: string
  type?: LecturerType
  department_id?: number
}

export interface PaginatedLecturers {
  items: Lecturer[]
  total: number
  page: number
  page_size: number
}

export const lecturersApi = {
  getAll: async (params?: LecturersQueryParams): Promise<PaginatedLecturers> => {
    const response = await api.get('/lecturers', { params })
    return response.data
  },

  getById: async (id: number): Promise<Lecturer> => {
    const response = await api.get(`/lecturers/${id}`)
    return response.data
  },

  getMe: async (): Promise<Lecturer> => {
    const response = await api.get('/lecturers/me')
    return response.data
  },

  create: async (data: CreateLecturerDTO): Promise<LecturerCreateResponse> => {
    const response = await api.post('/lecturers', data)
    return response.data
  },

  update: async (id: number, data: UpdateLecturerDTO): Promise<Lecturer> => {
    const response = await api.put(`/lecturers/${id}`, data)
    return response.data
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/lecturers/${id}`)
  },
}
