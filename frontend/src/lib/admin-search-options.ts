import { classesApi } from '@/api/classes'
import { lecturersApi } from '@/api/lecturers'

export const searchLecturers = async (query: string) => {
  const result = await lecturersApi.getAll({ page: 1, page_size: 100, q: query || undefined })
  return { items: result.items.map((lecturer) => ({ value: String(lecturer.id), label: `${lecturer.full_name} (${lecturer.code})` })), total: result.total }
}

export const searchClasses = async (query: string) => {
  const result = await classesApi.getAll({ page: 1, page_size: 100, q: query || undefined })
  return { items: result.items.map((item) => ({ value: String(item.id), label: `${item.code}${item.subject_name ? ` · ${item.subject_name}` : ''}` })), total: result.total }
}
