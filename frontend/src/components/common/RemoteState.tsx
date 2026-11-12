import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'

export function RemoteState({ loading, error = '', empty = '', onRetry }: {
  loading: boolean; error?: string; empty?: string; onRetry?: () => void
}) {
  if (loading) return <div className="space-y-3" aria-label="Đang tải"><Skeleton className="h-16 w-full" /><Skeleton className="h-32 w-full" /></div>
  if (error) return <div role="alert" className="space-y-3 rounded-md border p-4"><p className="text-destructive">{error}</p>{onRetry && <Button variant="outline" onClick={onRetry}>Thử lại</Button>}</div>
  if (!empty) return null
  return <p className="rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground">{empty}</p>
}

export function Pagination({ page, total, pageSize = 20, loading, onChange }: {
  page: number; total: number; pageSize?: number; loading: boolean; onChange: (page: number) => void
}) {
  return <div className="flex flex-wrap items-center justify-between gap-2 text-sm"><span>{total} kết quả · Trang {page}/{Math.max(1, Math.ceil(total / pageSize))}</span><div className="flex gap-2"><Button size="sm" variant="outline" disabled={loading || page <= 1} onClick={() => onChange(page - 1)}>Trang trước</Button><Button size="sm" variant="outline" disabled={loading || page * pageSize >= total} onClick={() => onChange(page + 1)}>Trang sau</Button></div></div>
}
