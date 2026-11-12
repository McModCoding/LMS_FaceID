export interface Department {
  id: number
  code: string
  name: string
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface DepartmentPayload {
  code?: string
  name?: string
  is_active?: boolean
}
