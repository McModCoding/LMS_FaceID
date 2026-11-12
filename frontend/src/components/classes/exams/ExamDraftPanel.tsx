import { useCallback, useEffect, useState } from 'react'
import { toast } from 'sonner'
import { examDraftApi, type ExamDraft } from '@/api/exam-drafts'
import { examManagementApi } from '@/api/exam-management'
import { getApiErrorMessage } from '@/lib/api-error'
import { RemoteState, Pagination } from '@/components/common/RemoteState'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ExamDraftForm } from './ExamDraftForm'
import { ExamManagement } from './ExamManagement'

const formatTime = (value: string) => new Intl.DateTimeFormat('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh', dateStyle: 'short', timeStyle: 'short' }).format(new Date(value))
const localInput = (value: string) => new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Ho_Chi_Minh', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(new Date(value)).replace(' ', 'T')
type Action = { exam: ExamDraft; type: 'publish' | 'close' | 'remove' | 'time' }

export function ExamDraftPanel({ classId, subjectId, canManage }: { classId: number; subjectId: number; canManage: boolean }) {
  const [items, setItems] = useState<ExamDraft[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<ExamDraft | null>(null)
  const [action, setAction] = useState<Action | null>(null)
  const [busy, setBusy] = useState(false)
  const [actionError, setActionError] = useState('')
  const [closeAt, setCloseAt] = useState('')
  const [managing, setManaging] = useState<ExamDraft | null>(null)
  const load = useCallback(async () => {
    setLoading(true); setError('')
    try { const data = await examDraftApi.list(classId, page); setItems(data.items); setTotal(data.total) }
    catch (err) { setError(getApiErrorMessage(err, 'Không thể tải danh sách bài kiểm tra.')) }
    finally { setLoading(false) }
  }, [classId, page])
  useEffect(() => { void load() }, [load])
  const choose = (exam: ExamDraft, type: Action['type']) => { setAction({ exam, type }); setActionError(''); setCloseAt(localInput(exam.close_at)) }
  async function execute() {
    if (!action) return
    setBusy(true); setActionError('')
    try {
      if (action.type === 'remove') await examDraftApi.remove(action.exam.id)
      if (action.type === 'publish') await examManagementApi.publish(action.exam.id)
      if (action.type === 'close') await examManagementApi.close(action.exam.id)
      if (action.type === 'time') {
        if (!closeAt) { setActionError('Hãy nhập giờ đóng.'); return }
        await examManagementApi.closeTime(action.exam.id, `${closeAt}:00+07:00`)
      }
      toast.success('Đã cập nhật bài kiểm tra.'); setAction(null); await load()
    } catch (cause) { setActionError(getApiErrorMessage(cause, 'Không cập nhật được bài kiểm tra.')) }
    finally { setBusy(false) }
  }
  const titles = { publish: 'Công bố bài kiểm tra?', close: 'Đóng đề và chốt bài đang làm?', remove: 'Xóa đề nháp?', time: 'Đổi giờ đóng đề' }
  return <Card className="min-w-0"><CardHeader><CardTitle>Bài kiểm tra</CardTitle><p className="text-sm text-muted-foreground">Soạn đề, kiểm tra cấu hình rồi công bố cho lớp. Đề được khóa nội dung từ khi có lượt làm đầu tiên.</p></CardHeader><CardContent className="space-y-4">
    {canManage && <Button onClick={() => { setEditing(null); setOpen(true) }}>Tạo đề nháp</Button>}
    <RemoteState loading={loading} error={error} onRetry={load} empty={!items.length ? (canManage ? 'Chưa có bài kiểm tra. Chọn “Tạo đề nháp” để bắt đầu.' : 'Chưa có bài kiểm tra. Lớp đã đóng chỉ cho phép xem.') : ''} />
    {!loading && !error && items.map(exam => <article key={exam.id} className="min-w-0 space-y-3 rounded-md border p-4" aria-label={exam.title}>
      <h3 className="break-words font-medium">{exam.title}</h3><p className="text-sm text-muted-foreground">{exam.status === 'draft' ? 'Đề nháp' : exam.status === 'published' ? 'Đã công bố' : 'Đã đóng'} · {exam.questions.length} câu · {exam.duration_min} phút · {Number(exam.total_points).toFixed(2)} điểm</p>
      <p className="text-sm">{formatTime(exam.open_at)} – {formatTime(exam.close_at)} (giờ Việt Nam)</p>
      {exam.has_attempts && <p className="text-sm text-muted-foreground">Đã có lượt làm: nội dung, đáp án và cấu hình đã khóa. Có thể điều chỉnh giờ đóng hoặc đóng đề.</p>}
      <div className="flex flex-wrap gap-2">
        {canManage && (exam.status === 'draft' || exam.status === 'published' && !exam.has_attempts) && <Button size="sm" variant="outline" onClick={() => { setEditing(exam); setOpen(true) }}>Sửa</Button>}
        {canManage && exam.status === 'draft' && <><Button size="sm" variant="outline" onClick={() => choose(exam, 'remove')}>Xóa</Button><Button size="sm" onClick={() => choose(exam, 'publish')}>Công bố</Button></>}
        {canManage && exam.status === 'published' && <><Button size="sm" variant="outline" onClick={() => choose(exam, 'time')}>Đổi giờ đóng</Button><Button size="sm" variant="outline" onClick={() => choose(exam, 'close')}>Đóng đề</Button></>}
        {exam.status !== 'draft' && <Button size="sm" variant="secondary" onClick={() => setManaging(exam)}>Bài làm & thống kê</Button>}
      </div>
    </article>)}
    <Pagination page={page} total={total} loading={loading} onChange={setPage} />
    <Dialog open={open} onOpenChange={setOpen}><DialogContent className="max-h-[90dvh] max-w-3xl overflow-y-auto"><DialogHeader><DialogTitle>{editing ? 'Sửa bài kiểm tra' : 'Tạo đề nháp'}</DialogTitle></DialogHeader>{open && <ExamDraftForm classId={classId} subjectId={subjectId} initial={editing} onCancel={() => setOpen(false)} onSaved={() => { setOpen(false); void load() }} />}</DialogContent></Dialog>
    <AlertDialog open={!!action} onOpenChange={value => { if (!value && !busy) setAction(null) }}><AlertDialogContent className="max-h-[90dvh] overflow-y-auto"><AlertDialogHeader><AlertDialogTitle>{action && titles[action.type]}</AlertDialogTitle><AlertDialogDescription className="break-words">{action?.exam.title}. {action?.type === 'publish' ? 'Nội dung và đáp án được đóng băng; sinh viên đang ghi danh nhận thông báo. Sau lượt đầu tiên chỉ được đổi giờ đóng hoặc đóng đề.' : action?.type === 'close' ? 'Tất cả lượt đang làm sẽ được tự động chốt theo các câu trả lời server đã nhận. Không thể mở lại đề đã đóng.' : action?.type === 'time' ? 'Giờ Việt Nam. Deadline không vượt thời lượng ban đầu; lượt đã nộp hoặc đã quá hạn không được mở lại. Rút ngắn giờ có thể chốt lượt đang làm.' : 'Đề nháp sẽ bị xóa; câu hỏi trong ngân hàng được giữ lại.'}</AlertDialogDescription></AlertDialogHeader>
      {action?.type === 'time' && <div className="space-y-2"><Label htmlFor="new-close-at">Giờ đóng mới</Label><Input id="new-close-at" type="datetime-local" value={closeAt} onChange={e => setCloseAt(e.target.value)} /></div>}
      {actionError && <p role="alert" className="text-sm text-destructive">{actionError}</p>}
      <AlertDialogFooter><AlertDialogCancel disabled={busy}>Hủy</AlertDialogCancel><AlertDialogAction disabled={busy} onClick={event => { event.preventDefault(); void execute() }}>{busy ? 'Đang xử lý…' : 'Xác nhận'}</AlertDialogAction></AlertDialogFooter>
    </AlertDialogContent></AlertDialog>
    <Dialog open={!!managing} onOpenChange={value => { if (!value) { setManaging(null); void load() } }}><DialogContent className="max-h-[90dvh] max-w-4xl overflow-y-auto"><DialogHeader><DialogTitle className="break-words">{managing?.title} · Bài làm & thống kê</DialogTitle></DialogHeader>{managing && <ExamManagement examId={managing.id} canGrade={canManage} />}</DialogContent></Dialog>
  </CardContent></Card>
}
