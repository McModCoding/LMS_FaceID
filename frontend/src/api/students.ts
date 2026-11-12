import api from './client'
import {
  Student,
  StudentStatus,
  CreateStudentDTO,
  UpdateStudentDTO,
  StudentCreateResponse,
  StudentImportPreview,
} from '../types/student'

export interface StudentsQueryParams {
  page?: number
  page_size?: number
  search?: string
  status?: StudentStatus
  department_id?: number
}

export interface PaginatedStudents {
  items: Student[]
  total: number
  page: number
  page_size: number
}

export const studentsApi = {
  getAll: async (params?: StudentsQueryParams): Promise<PaginatedStudents> => {
    const response = await api.get('/students', { params })
    return response.data
  },

  getById: async (id: number): Promise<Student> => {
    const response = await api.get(`/students/${id}`)
    return response.data
  },

  getMe: async (): Promise<Student> => {
    const response = await api.get('/students/me')
    return response.data
  },

  create: async (data: CreateStudentDTO): Promise<StudentCreateResponse> => {
    const response = await api.post('/students', data)
    return response.data
  },

  update: async (id: number, data: UpdateStudentDTO): Promise<Student> => {
    const response = await api.put(`/students/${id}`, data)
    return response.data
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/students/${id}`)
  },

  importPreview: async (file: File): Promise<StudentImportPreview> => {
    const formData = new FormData()
    formData.append('file', file)
    const response = await api.post('/students/import/preview', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return response.data
  },

  importConfirm: async (validRows: object[]): Promise<Blob> => {
    const response = await api.post(
      '/students/import/confirm',
      { valid_rows: validRows },
      { responseType: 'blob' }
    )
    return response.data
  },

  downloadTemplate: async (): Promise<Blob> => {
    const response = await api.get('/students/import/template', { responseType: 'blob' })
    return response.data
  },

  exportExcel: async (params?: StudentsQueryParams): Promise<Blob> => {
    const response = await api.get('/students/export', { params, responseType: 'blob' })
    return response.data
  },
}
