import api from './client'
import { Semester, CreateSemesterDTO, UpdateSemesterDTO } from '../types/semester'

export const semestersApi = {
  getAll: async (): Promise<Semester[]> => {
    const response = await api.get('/semesters')
    return response.data
  },

  getById: async (id: number): Promise<Semester> => {
    const response = await api.get(`/semesters/${id}`)
    return response.data
  },

  create: async (data: CreateSemesterDTO): Promise<Semester> => {
    const response = await api.post('/semesters', data)
    return response.data
  },

  update: async (id: number, data: UpdateSemesterDTO): Promise<Semester> => {
    const response = await api.put(`/semesters/${id}`, data)
    return response.data
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/semesters/${id}`)
  },
}
