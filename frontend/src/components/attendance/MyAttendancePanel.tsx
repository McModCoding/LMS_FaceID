import { useCallback, useEffect, useState } from 'react'
import dayjs from 'dayjs'
import { AlertTriangle, BookOpenCheck, CheckCircle2, Clock3, XCircle } from 'lucide-react'
import { RemoteState } from '@/components/common/RemoteState'
import { getApiErrorMessage } from '@/lib/api-error'
import api from '@/api/client'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { AttendanceStatusBadge } from '@/components/common/status-badge'

type AttendanceEntry = { session_id: number; session_no: number; date: string; start_time: string; end_time: string; room: string; display_status: 'present' | 'late' | 'absent' | 'excused' | 'pending' }
type Data = { summary: { attendance_score: number | null; total_sessions: number; present_count: number; late_count: number; absent_count: number; excused_count: number; has_warning: boolean; warning_threshold: number }; records: AttendanceEntry[] }

export function MyAttendancePanel({ classId }: { classId: number }) {
  const [data, setData] = useState<Data | null>(null)
  const [loading, setLoading] = useState(true)

  const [error, setError] = useState('')
  const load = useCallback(() => {
    setLoading(true); setError('')
    api.get<Data[]>(`/me/attendance?class_id=${classId}`)
      .then((r) => setData(r.data[0] ?? null))
      .catch(cause => setError(getApiErrorMessage(cause, 'Không thể tải chuyên cần.')))
      .finally(() => setLoading(false))
  }, [classId])
  useEffect(() => { load() }, [load])

  if (loading) return <div className="space-y-4"><Skeleton className="h-40 w-full" /><Skeleton className="h-64 w-full" /></div>
  if (error) return <RemoteState loading={false} error={error} onRetry={load} />
  if (!data) return <div className="rounded-lg border bg-card py-10 text-center text-sm text-muted-foreground">Chưa có dữ liệu chuyên cần. Điểm chuyên cần sẽ xuất hiện sau khi lớp có buổi học đã đóng.</div>

  const s = data.summary
  return <div className="space-y-4">
    {s.has_warning && <Alert variant="destructive"><AlertTriangle className="h-4 w-4" /><AlertTitle>Cảnh báo chuyên cần</AlertTitle><AlertDescription>Bạn đã vắng {s.absent_count} buổi; ngưỡng cảnh báo của lớp là từ {s.warning_threshold} buổi vắng.</AlertDescription></Alert>}
    <Card>
      <CardHeader className="pb-3"><div className="flex flex-wrap items-start justify-between gap-3"><div><CardTitle className="flex items-center gap-2 text-base"><BookOpenCheck className="h-4 w-4 text-primary" /> Chuyên cần của tôi</CardTitle><CardDescription>Chỉ tính các buổi học đã đóng.</CardDescription></div><Badge variant="outline">Điểm chuyên cần: {s.attendance_score ?? 'Chưa có'}</Badge></div></CardHeader>
      <CardContent><div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="rounded-md border p-3"><div className="flex items-center gap-1 text-sm text-muted-foreground"><CheckCircle2 className="h-4 w-4 text-success" /> Có mặt</div><p className="mt-1 text-2xl font-semibold">{s.present_count}</p></div>
        <div className="rounded-md border p-3"><div className="flex items-center gap-1 text-sm text-muted-foreground"><Clock3 className="h-4 w-4 text-warning" /> Đi muộn</div><p className="mt-1 text-2xl font-semibold">{s.late_count}</p></div>
        <div className="rounded-md border p-3"><div className="flex items-center gap-1 text-sm text-muted-foreground"><XCircle className="h-4 w-4 text-destructive" /> Vắng</div><p className="mt-1 text-2xl font-semibold">{s.absent_count}</p></div>
        <div className="rounded-md border p-3"><div className="text-sm text-muted-foreground">Có phép / tổng buổi</div><p className="mt-1 text-2xl font-semibold">{s.excused_count} <span className="text-base font-normal text-muted-foreground">/ {s.total_sessions}</span></p></div>
      </div></CardContent>
    </Card>
    <div className="rounded-xl border bg-card md:hidden"><h3 className="border-b px-4 py-3 font-semibold">Lịch sử từng buổi</h3>{data.records.length ? <ul className="divide-y">{data.records.map(r => <li key={r.session_id} className="flex flex-wrap items-center justify-between gap-2 p-4"><div><p className="font-medium">Buổi {r.session_no} · {dayjs(r.date).format('DD/MM/YYYY')}</p><p className="text-sm text-muted-foreground">{r.start_time.slice(0, 5)}–{r.end_time.slice(0, 5)} · {r.room}</p></div><AttendanceStatusBadge status={r.display_status} /></li>)}</ul> : <p className="p-4 text-sm text-muted-foreground">Chưa có buổi học nào để hiển thị.</p>}</div>
    <div className="hidden rounded-md border bg-card md:block"><div className="border-b px-4 py-3"><h3 className="text-sm font-semibold">Lịch sử từng buổi</h3></div><Table><TableHeader><TableRow><TableHead>Buổi</TableHead><TableHead>Ngày</TableHead><TableHead className="hidden sm:table-cell">Giờ</TableHead><TableHead className="hidden md:table-cell">Phòng</TableHead><TableHead>Trạng thái</TableHead></TableRow></TableHeader><TableBody>{data.records.map((r) => <TableRow key={r.session_id}><TableCell className="font-medium">{r.session_no}</TableCell><TableCell>{dayjs(r.date).format('DD/MM/YYYY')}</TableCell><TableCell className="hidden sm:table-cell">{r.start_time.slice(0, 5)}–{r.end_time.slice(0, 5)}</TableCell><TableCell className="hidden md:table-cell">{r.room}</TableCell><TableCell><AttendanceStatusBadge status={r.display_status} /></TableCell></TableRow>)}</TableBody></Table></div>
  </div>
}
