import { useCallback, useEffect, useState } from 'react'
import dayjs from 'dayjs'
import { toast } from 'sonner'
import { classesApi } from '@/api/classes'
import { LeaveList, LeaveRequest, LeaveStatus, leaveApi } from '@/api/leave-requests'
import { Session } from '@/types/session'
import { getApiErrorMessage } from '@/lib/api-error'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Pagination, RemoteState } from '@/components/common/RemoteState'

export function LeaveRequestsPanel({ classId, student = false, writable = true }: { classId: number; student?: boolean; writable?: boolean }) {
  const [data, setData] = useState<LeaveList>({ items: [], total: 0, page: 1, page_size: 20 })
  const [page, setPage] = useState(1)
  const [filter, setFilter] = useState<LeaveStatus | 'all'>('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [creating, setCreating] = useState(false)
  const [sessionId, setSessionId] = useState('')
  const [sessions, setSessions] = useState<Session[]>([])
  const [sessionPage, setSessionPage] = useState(1)
  const [sessionTotal, setSessionTotal] = useState(0)
  const [sessionLoading, setSessionLoading] = useState(false)
  const [sessionError, setSessionError] = useState('')
  const [reason, setReason] = useState('')
  const [formError, setFormError] = useState('')
  const [action, setAction] = useState<{ item: LeaveRequest; decision: 'approve' | 'reject' | 'cancel' } | null>(null)
  const [reviewNote, setReviewNote] = useState('')
  const load = useCallback(async () => {
    setLoading(true); setError('')
    try { setData(await leaveApi.list(student, { class_id: classId, page, status: filter === 'all' ? undefined : filter })) }
    catch (cause) { setError(getApiErrorMessage(cause, 'Không thể tải đơn xin vắng.')) }
    finally { setLoading(false) }
  }, [classId, page, filter, student])
  useEffect(() => { void load() }, [load])
  const loadSessions = useCallback(async () => {
    setSessionLoading(true); setSessionError('')
    try { const result = await classesApi.getSessions(classId, { page: sessionPage, page_size: 20 }); setSessions(result.items); setSessionTotal(result.total) }
    catch (cause) { setSessionError(getApiErrorMessage(cause, 'Không thể tải buổi học.')) }
    finally { setSessionLoading(false) }
  }, [classId, sessionPage])
  useEffect(() => { if (creating) void loadSessions() }, [creating, loadSessions])
  const create = async (event: React.FormEvent) => {
    event.preventDefault(); setBusy(true); setFormError('')
    try { await leaveApi.create(Number(sessionId), reason.trim()); setCreating(false); toast.success('Đã gửi đơn xin vắng.'); await load() }
    catch (cause) { setFormError(getApiErrorMessage(cause, 'Không thể gửi đơn.')) }
    finally { setBusy(false) }
  }
  const process = async () => {
    if (!action) return
    setBusy(true); setFormError('')
    try {
      if (action.decision === 'cancel') await leaveApi.cancel(action.item.id)
      else await leaveApi.review(action.item.id, action.decision, reviewNote.trim())
      setAction(null); toast.success('Đã xử lý đơn xin vắng.'); await load()
    } catch (cause) { setFormError(getApiErrorMessage(cause, 'Không thể xử lý đơn.')) }
    finally { setBusy(false) }
  }
  return <Card><CardHeader><div className="flex flex-wrap items-center justify-between gap-3"><CardTitle className="text-base">Đơn xin vắng</CardTitle>{student && writable && <Button onClick={() => { setReason(''); setSessionId(''); setSessionPage(1); setFormError(''); setCreating(true) }}>Gửi đơn xin vắng</Button>}</div><CardDescription>Đơn được duyệt chỉ cập nhật bản ghi vắng mặc định; điểm danh đã xử lý được giữ nguyên. Buổi đã đóng áp dụng cửa sổ sửa theo quyền.</CardDescription></CardHeader><CardContent className="space-y-4">
    <Select value={filter} onValueChange={value => { setFilter(value as typeof filter); setPage(1) }}><SelectTrigger className="w-full sm:w-56" aria-label="Lọc trạng thái đơn"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="all">Tất cả trạng thái</SelectItem><SelectItem value="pending">Chờ duyệt</SelectItem><SelectItem value="approved">Đã duyệt</SelectItem><SelectItem value="rejected">Từ chối / đã hủy</SelectItem></SelectContent></Select>
    {loading || error || !data.items.length ? <RemoteState loading={loading} error={error} empty={student ? 'Chưa có đơn phù hợp. Chọn Gửi đơn xin vắng để tạo đơn cho buổi học.' : 'Chưa có đơn phù hợp. Đơn sinh viên gửi sẽ xuất hiện tại đây.'} onRetry={load} /> : data.items.map(item => <article key={item.id} className="space-y-2 rounded-md border p-4 text-sm"><div className="flex flex-wrap justify-between gap-2"><p className="font-medium">{!student && `${item.student_name} · ${item.student_code} · `}Buổi {item.session_no} · {dayjs(item.session_date).format('DD/MM/YYYY')}</p><Badge variant={item.status === 'approved' ? 'success' : item.status === 'pending' ? 'warning' : 'secondary'}>{item.status === 'pending' ? 'Chờ duyệt' : item.status === 'approved' ? 'Đã duyệt' : item.reviewed_at ? 'Từ chối' : 'Đã hủy'}</Badge></div><p className="whitespace-pre-wrap break-words">{item.reason}</p><p className="text-muted-foreground">Gửi lúc {dayjs(item.created_at).format('DD/MM/YYYY HH:mm')}{item.reviewed_at && ` · Xử lý bởi ${item.reviewer_name} lúc ${dayjs(item.reviewed_at).format('DD/MM/YYYY HH:mm')}`}</p>{item.review_note && <p className="break-words">Phản hồi: {item.review_note}</p>}{writable && item.status === 'pending' && <div className="flex flex-wrap gap-2">{(student ? ['cancel'] as const : ['approve', 'reject'] as const).map(decision => <Button key={decision} variant={decision === 'approve' ? 'default' : 'outline'} size="sm" onClick={() => { setAction({ item, decision }); setReviewNote(''); setFormError('') }}>{decision === 'cancel' ? 'Hủy đơn' : decision === 'approve' ? 'Duyệt đơn' : 'Từ chối'}</Button>)}</div>}</article>)}
    <Pagination page={page} total={data.total} loading={loading} onChange={setPage} />
    <Dialog open={creating} onOpenChange={value => !busy && setCreating(value)}><DialogContent className="max-h-[85vh] overflow-y-auto"><DialogHeader><DialogTitle>Gửi đơn xin vắng</DialogTitle><DialogDescription>Chọn buổi chưa bị hủy. Server kiểm tra thời hạn 7 ngày và không cho gửi trùng đơn đang chờ.</DialogDescription></DialogHeader><form className="space-y-4" onSubmit={create}>
      {sessionError ? <RemoteState loading={false} error={sessionError} empty="" onRetry={loadSessions} /> : <><Label htmlFor="leave-session">Buổi học</Label><Select value={sessionId} onValueChange={setSessionId}><SelectTrigger id="leave-session"><SelectValue placeholder={sessionLoading ? 'Đang tải buổi học…' : 'Chọn buổi học'} /></SelectTrigger><SelectContent>{sessions.filter(item => item.status !== 'cancelled').map(item => <SelectItem key={item.id} value={String(item.id)}>Buổi {item.session_no} · {dayjs(item.date).format('DD/MM/YYYY')} · {item.start_time.slice(0, 5)}</SelectItem>)}</SelectContent></Select>{!sessionLoading && !sessions.length && <p className="text-sm text-muted-foreground">Lớp chưa có buổi học. Liên hệ giảng viên để kiểm tra lịch.</p>}<Pagination page={sessionPage} total={sessionTotal} loading={sessionLoading} onChange={setSessionPage} /></>}
      <div className="space-y-2"><Label htmlFor="leave-reason">Lý do (tối đa 500 ký tự)</Label><Textarea id="leave-reason" required maxLength={500} value={reason} onChange={event => setReason(event.target.value)} /></div>{formError && <p role="alert" className="text-sm text-destructive">{formError}</p>}<Button disabled={busy || !sessionId || !reason.trim() || !!sessionError} type="submit">{busy ? 'Đang gửi…' : 'Gửi đơn'}</Button></form></DialogContent></Dialog>
    <Dialog open={!!action} onOpenChange={value => !value && !busy && setAction(null)}><DialogContent><DialogHeader><DialogTitle>{action?.decision === 'cancel' ? 'Hủy đơn xin vắng?' : action?.decision === 'approve' ? 'Duyệt đơn xin vắng?' : 'Từ chối đơn xin vắng?'}</DialogTitle><DialogDescription>{action?.decision === 'cancel' ? 'Đơn sẽ ngừng chờ duyệt. Bạn có thể gửi lại nếu còn đủ điều kiện.' : 'Quyết định được lưu và gửi thông báo cho sinh viên. Duyệt đơn không ghi đè điểm danh đã xử lý.'}</DialogDescription></DialogHeader>{action?.decision !== 'cancel' && <div className="space-y-2"><Label htmlFor="leave-review">Phản hồi (tối đa 500 ký tự)</Label><Textarea id="leave-review" maxLength={500} value={reviewNote} onChange={event => setReviewNote(event.target.value)} /></div>}{formError && <p role="alert" className="text-sm text-destructive">{formError}</p>}<div className="flex justify-end gap-2"><Button variant="outline" disabled={busy} onClick={() => setAction(null)}>Quay lại</Button><Button disabled={busy} onClick={process}>{busy ? 'Đang lưu…' : 'Xác nhận'}</Button></div></DialogContent></Dialog>
  </CardContent></Card>
}
