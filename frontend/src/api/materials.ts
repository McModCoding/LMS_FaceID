import api from './client'

export interface Material { id: number; class_id: number; title: string; description: string | null; url: string | null; filename: string | null; has_file: boolean; created_at: string }
export const materialsApi = {
  list: async (classId: number, page: number) => (await api.get<{ items: Material[]; total: number }>(`/classes/${classId}/materials`, { params: { page, page_size: 20 } })).data,
  create: async (classId: number, data: FormData) => (await api.post(`/classes/${classId}/materials`, data, { headers: { 'Content-Type': 'multipart/form-data' } })).data,
  update: async (id: number, title: string, description: string) => (await api.patch(`/materials/${id}`, { title, description })).data,
  remove: async (id: number) => api.delete(`/materials/${id}`),
  download: async (id: number): Promise<Blob> => (await api.get(`/materials/${id}/file`, { responseType: 'blob' })).data,
}
