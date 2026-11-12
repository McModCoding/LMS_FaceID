type ApiErrorPayload = {
  response?: {
    data?: {
      error?: { message?: string }
      detail?: { message?: string } | string
    }
  }
}

export function getApiErrorMessage(error: unknown, fallback: string): string {
  const data = (error as ApiErrorPayload | null | undefined)?.response?.data
  if (typeof data?.detail === 'string') return data.detail
  return data?.error?.message || data?.detail?.message || fallback
}
