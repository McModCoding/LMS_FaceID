import { useCallback, useEffect, useState } from 'react'
import dayjs from 'dayjs'
import { toast } from 'sonner'
import api from '@/api/client'
import { getApiErrorMessage } from '@/lib/api-error'
import { downloadBlob } from '@/lib/download'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { AttendanceStatusBadge } from '@/components/common/status-badge'
import { Pagination, RemoteState } from '@/components/common/RemoteState'
import { AttendanceStatus } from '@/types/attendance'

interface Summary { student_id: number; student_code: string; full_name: string; is_dropped: boolean; total_sessions: number; present_count: number; late_count: number; absent_count: number; excused_count: number; attendance_score: number | string | null; attendance_rate: number | null; has_warning: boolean }
interface Matrix { sessions: { id: number; session_no: number; date: string }[]; items: { cells: { status: AttendanceStatus | null }[] }[] }

export function AttendanceReportPanel({ classId }: { classId: number }) {
  const [data, setData] = useState<{ items: Summary[]; total: number }>({ items: [], total: 0 })
  const [page, setPage] = useState(1)
  const [query, setQuery] = useState('')
  const [search, setSearch] = useState('')
  const [warning, setWarning] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState<Summary | null>(null)
  const [matrix, setMatrix] = useState<Matrix | null>(null)
  const [detailError, setDetailError] = useState('')
  const [detailLoading, setDetailLoading] = useState(false)
  const load = useCallback(async () => {
    setLoading(true); setError('')
    try { setData((await api.get(`/classes/${classId}/attendance-report`, { params: { q: search || undefined, warning, page, page_size: 20 } })).data) }
    catch (cause) { setError(getApiErrorMessage(cause, 'Không thể tải báo cáo chuyên cần.')) }
    finally { setLoading(false) }
  }, [classId, page, search, warning])
  useEffect(() => { void load() }, [load])
  const loadDetail = useCallback(async () => {
    if (!selected) return
    setMatrix(null); setDetailError(''); setDetailLoading(true)
    try { setMatrix((await api.get(`/classes/${classId}/attendance-matrix`, { params: { student_id: selected.student_id } })).data) }
    catch (cause) { setDetailError(getApiErrorMessage(cause, 'Không thể tải lịch sử chuyên cần.')) }
    finally { setDetailLoading(false) }
  }, [classId, selected])
  useEffect(() => { void loadDetail() }, [loadDetail])
  const download = async () => {
    try { const result = await api.get(`/classes/${classId}/attendance/export`, { responseType: 'blob' }); downloadBlob(result.data, `chuyen-can-lop-${classId}.xlsx`) }
    catch (cause) { toast.error(getApiErrorMessage(cause, 'Không thể xuất báo cáo.')) }
  }
  return <Card><CardHeader><div className="flex flex-wrap items-center justify-between gap-2"><CardTitle className="text-base">Báo cáo chuyên cần</CardTitle><Button variant="outline" onClick={download}>Xuất Excel toàn lớp</Button></div><CardDescription>Chỉ tính bản ghi thuộc buổi đã đóng. Tỷ lệ tham dự = (có mặt + trễ) / tổng buổi có bản ghi; điểm chuyên cần tính theo trọng số của lớp. Excel gồm toàn lớp, không theo bộ lọc màn hình.</CardDescription></CardHeader><CardContent className="space-y-4">
    <form className="flex flex-wrap gap-2" onSubmit={event => { event.preventDefault(); setSearch(query.trim()); setPage(1) }}><Input className="w-full sm:w-72" aria-label="Tìm sinh viên trong báo cáo" placeholder="MSSV hoặc họ tên" value={query} onChange={event => setQuery(event.target.value)} /><Button type="submit" variant="outline">Tìm kiếm</Button><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={warning} onChange={event => { setWarning(event.target.checked); setPage(1) }} />Chỉ sinh viên có cảnh báo</label></form>
    {loading || error || !data.items.length ? <RemoteState loading={loading} error={error} empty="Chưa có sinh viên phù hợp. Kiểm tra danh sách lớp hoặc bỏ bộ lọc." onRetry={load} /> : <div className="overflow-x-auto rounded-md border"><Table><TableHeader><TableRow><TableHead>Sinh viên</TableHead><TableHead>Tổng buổi</TableHead><TableHead>Có mặt / Trễ / Vắng / Phép</TableHead><TableHead>Tỷ lệ</TableHead><TableHead>Điểm</TableHead><TableHead>Cảnh báo</TableHead><TableHead>Chi tiết</TableHead></TableRow></TableHeader><TableBody>{data.items.map(row => <TableRow key={row.student_id}><TableCell><p className="font-medium">{row.full_name}</p><p className="text-xs text-muted-foreground">{row.student_code}{row.is_dropped ? ' · Đã rút' : ''}</p></TableCell><TableCell>{row.total_sessions}</TableCell><TableCell>{row.present_count} / {row.late_count} / {row.absent_count} / {row.excused_count}</TableCell><TableCell>{row.attendance_rate == null ? 'Chưa có' : `${(row.attendance_rate * 100).toFixed(1)}%`}</TableCell><TableCell>{row.attendance_score ?? 'Chưa có'}</TableCell><TableCell>{row.has_warning ? <Badge variant="warning">Vắng nhiều</Badge> : '—'}</TableCell><TableCell><Button variant="outline" size="sm" onClick={() => setSelected(row)}>Lịch sử</Button></TableCell></TableRow>)}</TableBody></Table></div>}
    <Pagination page={page} total={data.total} loading={loading} onChange={setPage} />
    <Dialog open={!!selected} onOpenChange={open => !open && setSelected(null)}><DialogContent className="max-h-[85vh] overflow-y-auto"><DialogHeader><DialogTitle>Chuyên cần: {selected?.full_name}</DialogTitle><DialogDescription>{selected?.student_code} · Chỉ các buổi đã đóng; không có bản ghi không tự tính là vắng.</DialogDescription></DialogHeader>{detailLoading || detailError || !matrix?.sessions.length ? <RemoteState loading={detailLoading} error={detailError} empty="Chưa có buổi đã đóng để xem lịch sử." onRetry={loadDetail} /> : <div className="space-y-2">{matrix.sessions.map((session, index) => <div key={session.id} className="flex flex-wrap justify-between gap-2 border-b py-2 text-sm"><span>Buổi {session.session_no} · {dayjs(session.date).format('DD/MM/YYYY')}</span>{matrix.items[0]?.cells[index]?.status ? <AttendanceStatusBadge status={matrix.items[0].cells[index].status!} /> : <span className="text-muted-foreground">Chưa có bản ghi</span>}</div>)}</div>}</DialogContent></Dialog>
  </CardContent></Card>
}
