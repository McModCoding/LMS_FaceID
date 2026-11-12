export interface Semester {
  id: number
  name: string
  start_date: string
  end_date: string
  is_current: boolean
  created_at?: string
  updated_at?: string
}

export interface CreateSemesterDTO {
  name: string
  start_date: string
  end_date: string
  is_current?: boolean
}

export interface UpdateSemesterDTO {
  name?: string
  start_date?: string
  end_date?: string
  is_current?: boolean
}
