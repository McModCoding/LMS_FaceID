import api from './client'
import { AuditLog } from '../types/user'

export interface AuditLogsQueryParams {
  page?: number
  page_size?: number
  action?: string
  entity?: string
  user_id?: number
  performer?: string
  date_from?: string
  date_to?: string
}

export interface PaginatedAuditLogs {
  items: AuditLog[]
  total: number
  page: number
  page_size: number
}

export const auditApi = {
  getLogs: async (params?: AuditLogsQueryParams): Promise<PaginatedAuditLogs> => {
    const response = await api.get('/audit-logs', { params })
    return response.data
  },
}
