import api from './client'
import { Department, DepartmentPayload } from '../types/department'

export const departmentsApi = {
  getAll: async (): Promise<Department[]> => (await api.get('/departments')).data,
  getById: async (id: number): Promise<Department> => (await api.get(`/departments/${id}`)).data,
  create: async (data: Required<Pick<DepartmentPayload, 'code' | 'name'>>): Promise<Department> => (await api.post('/departments', data)).data,
  update: async (id: number, data: DepartmentPayload): Promise<Department> => (await api.put(`/departments/${id}`, data)).data,
  deactivate: async (id: number): Promise<void> => { await api.delete(`/departments/${id}`) },
}
