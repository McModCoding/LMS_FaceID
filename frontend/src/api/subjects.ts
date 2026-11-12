import api from './client'
import { Subject, CreateSubjectDTO, UpdateSubjectDTO } from '../types/subject'

export const subjectsApi = {
  getAll: async (query?: string, departmentId?: number): Promise<Subject[]> => {
    const response = await api.get('/subjects', {
      params: { ...(query ? { q: query } : {}), ...(departmentId !== undefined ? { department_id: departmentId } : {}) },
    })
    return response.data
  },

  getById: async (id: number): Promise<Subject> => {
    const response = await api.get(`/subjects/${id}`)
    return response.data
  },

  create: async (data: CreateSubjectDTO): Promise<Subject> => {
    const response = await api.post('/subjects', data)
    return response.data
  },

  update: async (id: number, data: UpdateSubjectDTO): Promise<Subject> => {
    const response = await api.put(`/subjects/${id}`, data)
    return response.data
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/subjects/${id}`)
  },
}
