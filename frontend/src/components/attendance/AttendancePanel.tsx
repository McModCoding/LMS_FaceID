import { useCallback, useEffect, useState } from 'react'
import dayjs from 'dayjs'
import { Check, Download, Loader2, Pencil, Play, Search, Square, ScanFace } from 'lucide-react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'

import { attendanceApi } from '@/api/attendance'
import { classesApi } from '@/api/classes'
import { sessionsApi } from '@/api/sessions'
import { AttendanceRecord, AttendanceStatus, SessionAttendanceResponse } from '@/types/attendance'
import { Session } from '@/types/session'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog'
import { AttendanceStatusBadge, SessionStatusBadge } from '@/components/common/status-badge'
import { getApiErrorMessage } from '@/lib/api-error'
import { downloadBlob } from '@/lib/download'

type Props = { classId: number }

export function AttendancePanel({ classId }: Props) {
  const [sessions, setSessions] = useState<Session[]>([])
  const [selectedSessionId, setSelectedSessionId] = useState<number | null>(null)
  const [attendance, setAttendance] = useState<SessionAttendanceResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [editing, setEditing] = useState<AttendanceRecord | null>(null)
  const [editStatus, setEditStatus] = useState<AttendanceStatus>('present')
  const [note, setNote] = useState('')
  const [sessionFilter, setSessionFilter] = useState<'all' | Session['status']>('all')
  const [sessionQuery, setSessionQuery] = useState('')
  const [closeConfirmOpen, setCloseConfirmOpen] = useState(false)

  const fetchSessions = useCallback(async () => {
    setLoading(true)
    try {
      const data = await classesApi.getSessions(classId, { page: 1, page_size: 100 })
      setSessions(data.items)
      setSelectedSessionId((current) => current && data.items.some((item) => item.id === current) ? current : (data.items[0]?.id ?? null))
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Không thể tải danh sách buổi học'))
    } finally { setLoading(false) }
  }, [classId])

  const fetchAttendance = useCallback(async () => {
    if (!selectedSessionId) { setAttendance(null); return }
    try { setAttendance(await attendanceApi.getSession(selectedSessionId)) }
    catch (error) { toast.error(getApiErrorMessage(error, 'Không thể tải danh sách điểm danh')) }
  }, [selectedSessionId])

  useEffect(() => { fetchSessions() }, [fetchSessions])
  useEffect(() => { fetchAttendance() }, [fetchAttendance])

  const selectedSession = sessions.find((item) => item.id === selectedSessionId)
  const visibleSessions = sessions.filter((item) => {
    const query = sessionQuery.trim().toLocaleLowerCase('vi-VN')
    const matchesQuery = !query || `buổi ${item.session_no} ${dayjs(item.date).format('DD/MM/YYYY')} ${item.room}`.toLocaleLowerCase('vi-VN').includes(query)
    return matchesQuery && (sessionFilter === 'all' || item.status === sessionFilter)
  })
  const refresh = async () => { await fetchSessions(); await fetchAttendance() }

  const changeSessionState = async (action: 'open' | 'close') => {
    if (!selectedSession) return
    setSaving(true)
    try {
      if (action === 'open') await sessionsApi.open(selectedSession.id)
      else await sessionsApi.close(selectedSession.id)
      toast.success(action === 'open' ? 'Đã mở buổi và tạo danh sách điểm danh.' : 'Đã đóng buổi học.')
      await refresh()
    } catch (error) { toast.error(getApiErrorMessage(error, action === 'open' ? 'Không thể mở buổi học' : 'Không thể đóng buổi học')) }
    finally { setSaving(false) }
  }

  const handleCheckIn = async (record: AttendanceRecord) => {
    if (!selectedSessionId) return
    setSaving(true)
    try { const result = await attendanceApi.checkIn(selectedSessionId, record.student_id); toast.success(result.message); await fetchAttendance() }
    catch (error) { toast.error(getApiErrorMessage(error, 'Không thể điểm danh sinh viên')) }
    finally { setSaving(false) }
  }

  const saveEdit = async () => {
    if (!editing || !selectedSessionId) return
    setSaving(true)
    try {
      await attendanceApi.update(selectedSessionId, editing.student_id, { status: editStatus, note: note.trim() || undefined, expected_status: editing.status })
      toast.success('Đã cập nhật điểm danh và lưu nhật ký thay đổi.')
      setEditing(null); setNote(''); await fetchAttendance()
    } catch (error) { toast.error(getApiErrorMessage(error, 'Không thể cập nhật điểm danh')) }
    finally { setSaving(false) }
  }

  const download = async () => {
    if (!selectedSessionId) return
    try {
      const file = await attendanceApi.exportSession(selectedSessionId)
      downloadBlob(file, `diem-danh-buoi-${selectedSessionId}.xlsx`)
    } catch (error) { toast.error(getApiErrorMessage(error, 'Không thể xuất Excel')) }
  }

  if (loading) return <div className="space-y-3"><Skeleton className="h-10 w-full" /><Skeleton className="h-64 w-full" /></div>
  if (!sessions.length) return <div className="rounded-lg border bg-card py-10 text-center text-sm text-muted-foreground">Chưa có buổi học để điểm danh. Hãy tạo lịch học trước.</div>

  return <div className="space-y-4">
    <Card><CardHeader className="pb-3"><CardTitle className="text-base">Điểm danh thủ công</CardTitle></CardHeader><CardContent className="space-y-3">
      <div className="grid gap-2 md:grid-cols-[minmax(0,1fr)_10rem_auto]">
        <div className="relative"><Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" /><Input className="pl-9" value={sessionQuery} onChange={(event) => setSessionQuery(event.target.value)} placeholder="Tìm theo buổi, ngày hoặc phòng" aria-label="Tìm buổi học" /></div>
        <Select value={sessionFilter} onValueChange={(value) => setSessionFilter(value as 'all' | Session['status'])}><SelectTrigger aria-label="Lọc trạng thái buổi học"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="all">Tất cả trạng thái</SelectItem><SelectItem value="open">Đang mở</SelectItem><SelectItem value="scheduled">Sắp diễn ra</SelectItem><SelectItem value="closed">Đã đóng</SelectItem><SelectItem value="cancelled">Đã hủy</SelectItem></SelectContent></Select>
        <Select value={selectedSessionId?.toString() ?? ''} onValueChange={(value) => setSelectedSessionId(Number(value))}><SelectTrigger className="min-w-0 md:min-w-80" aria-label="Chọn buổi học"><SelectValue placeholder="Chọn buổi học" /></SelectTrigger><SelectContent>{visibleSessions.length ? visibleSessions.map((item) => <SelectItem key={item.id} value={item.id.toString()}>Buổi {item.session_no} · {dayjs(item.date).format('DD/MM/YYYY')} · {item.start_time.slice(0, 5)} · {item.status === 'open' ? 'Đang mở' : item.status === 'scheduled' ? 'Sắp diễn ra' : item.status === 'closed' ? 'Đã đóng' : 'Đã hủy'}</SelectItem>) : <div className="px-2 py-4 text-sm text-muted-foreground">Không có buổi phù hợp.</div>}</SelectContent></Select>
      </div>
      <div className="flex flex-wrap gap-2 items-center">
        {selectedSession?.status === 'scheduled' && <Button size="sm" disabled={saving} onClick={() => changeSessionState('open')}><Play className="mr-2 h-4 w-4" />Mở buổi</Button>}
        {selectedSession?.status === 'open' && <Button size="sm" variant="destructive" disabled={saving} onClick={() => setCloseConfirmOpen(true)}><Square className="mr-2 h-4 w-4" />Đóng buổi</Button>}
        {selectedSession?.status === 'open' && <Button size="sm" variant="outline" asChild><Link to={`/lecturer/sessions/${selectedSession.id}/live`}><ScanFace className="mr-2 h-4 w-4" />Điểm danh trực tiếp</Link></Button>}
        <Button size="sm" variant="outline" onClick={download}><Download className="mr-2 h-4 w-4" />Excel</Button>
      </div>
      {selectedSession && <SessionStatusBadge status={selectedSession.status} />}
      {attendance && <div className="flex flex-wrap gap-2 text-sm"><Badge variant="success">Có mặt: {attendance.summary.present}</Badge><Badge variant="warning">Đi muộn: {attendance.summary.late}</Badge><Badge variant="destructive">Vắng: {attendance.summary.absent}</Badge><Badge variant="secondary">Có phép: {attendance.summary.excused}</Badge><Badge variant="outline">Chưa điểm danh: {attendance.summary.pending}</Badge></div>}
    </CardContent></Card>
    {!attendance ? <Skeleton className="h-64 w-full" /> : <div className="rounded-md border bg-card overflow-x-auto"><Table><TableHeader><TableRow><TableHead>MSSV</TableHead><TableHead>Họ tên</TableHead><TableHead>Trạng thái</TableHead><TableHead>Nguồn</TableHead><TableHead className="text-right">Thao tác</TableHead></TableRow></TableHeader><TableBody>
      {attendance.items.map((record) => <TableRow key={record.id}><TableCell>{record.student_code}</TableCell><TableCell className="font-medium">{record.full_name}</TableCell><TableCell><AttendanceStatusBadge status={record.display_status} /></TableCell><TableCell className="hidden md:table-cell">{record.source === 'manual' ? 'Thủ công' : record.source === 'system' ? 'Hệ thống' : record.source === 'leave' ? 'Đơn xin vắng' : 'FaceID'}</TableCell><TableCell className="text-right space-x-1">
        {selectedSession?.status === 'open' && record.display_status === 'pending' && <Button size="sm" disabled={saving} onClick={() => handleCheckIn(record)}><Check className="mr-1 h-4 w-4" />Có mặt</Button>}
        {attendance.can_edit && <Button disabled={saving} size="sm" variant="outline" aria-label={`Sửa điểm danh ${record.full_name ?? record.student_code ?? ''}`} onClick={() => { setEditing(record); setEditStatus(record.status); setNote('') }}><Pencil className="h-4 w-4" /></Button>}
      </TableCell></TableRow>)}
    </TableBody></Table></div>}
    <Dialog open={Boolean(editing)} onOpenChange={(open) => !open && setEditing(null)}><DialogContent><DialogHeader><DialogTitle>Sửa điểm danh</DialogTitle></DialogHeader><div className="space-y-4 py-2"><p className="text-sm text-muted-foreground">{editing?.student_code} · {editing?.full_name}</p><div className="space-y-2"><Label>Trạng thái</Label><Select value={editStatus} onValueChange={(value) => setEditStatus(value as AttendanceStatus)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{(['present', 'late', 'absent', 'excused'] as AttendanceStatus[]).map((item) => <SelectItem key={item} value={item}>{item === 'present' ? 'Có mặt' : item === 'late' ? 'Đi muộn' : item === 'absent' ? 'Vắng' : 'Có phép'}</SelectItem>)}</SelectContent></Select></div><div className="space-y-2"><Label>Ghi chú</Label><Input value={note} onChange={(event) => setNote(event.target.value)} placeholder="Bắt buộc khi sửa buổi đã đóng hoặc bản ghi đã xử lý" /></div></div><DialogFooter><Button variant="outline" onClick={() => setEditing(null)}>Hủy</Button><Button disabled={saving} onClick={saveEdit}>{saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Lưu thay đổi</Button></DialogFooter></DialogContent></Dialog>
    <AlertDialog open={closeConfirmOpen} onOpenChange={setCloseConfirmOpen}><AlertDialogContent><AlertDialogHeader><AlertDialogTitle>Đóng buổi học?</AlertDialogTitle><AlertDialogDescription>Các sinh viên chưa điểm danh sẽ được giữ trạng thái vắng. Sau khi đóng, việc chỉnh sửa cần tuân theo quyền và thời hạn của hệ thống.</AlertDialogDescription></AlertDialogHeader><AlertDialogFooter><AlertDialogCancel>Hủy</AlertDialogCancel><AlertDialogAction className="bg-destructive text-destructive-foreground hover:bg-destructive/90" disabled={saving} onClick={() => { setCloseConfirmOpen(false); changeSessionState('close') }}>Đóng buổi</AlertDialogAction></AlertDialogFooter></AlertDialogContent></AlertDialog>
  </div>
}
