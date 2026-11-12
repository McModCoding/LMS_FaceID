export type UserRole = 'admin' | 'lecturer' | 'student'

export interface User {
  id: number
  username: string
  email: string
  role: UserRole
  is_active: boolean
  must_change_password?: boolean
  last_login_at?: string | null
  updated_at?: string
}

export interface Token {
  access_token: string
  refresh_token: string
  token_type: string
  user: User
}

export interface AuditLog {
  id: number
  user_id?: number | null
  username?: string | null
  action: string
  entity: string
  entity_id?: string | number | null
  detail?: Record<string, any> | string | null
  ip?: string | null
  created_at: string
}
