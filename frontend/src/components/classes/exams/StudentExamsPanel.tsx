import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertCircle, BookOpenCheck, Clock3, FileQuestion, Maximize, RefreshCw } from 'lucide-react'
import { toast } from 'sonner'

import { studentExamsApi, type StudentExam, type StudentExamStatus } from '@/api/student-exams'
import { getApiErrorMessage } from '@/lib/api-error'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Pagination } from '@/components/common/RemoteState'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { StudentExamResults } from './StudentExamResults'
import { eventLabels } from '@/api/exam-management'
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog'

const labels: Record<StudentExamStatus, { text: string; variant: 'default' | 'secondary' | 'success' | 'warning' | 'outline' }> = {
  upcoming: { text: 'Chưa mở', variant: 'secondary' },
  available: { text: 'Đang mở', variant: 'success' },
  in_progress: { text: 'Đang làm', variant: 'default' },
  retry_available: { text: 'Còn lượt làm', variant: 'success' },
  completed: { text: 'Đã dùng hết lượt', variant: 'outline' },
  closed: { text: 'Đã đóng', variant: 'outline' },
}

const localDateTime = (value: string) => new Intl.DateTimeFormat('vi-VN', {
  dateStyle: 'short', timeStyle: 'short', timeZone: 'Asia/Ho_Chi_Minh',
}).format(new Date(value))

export function StudentExamsPanel({ classId }: { classId: number }) {
  const navigate = useNavigate()
  const [items, setItems] = useState<StudentExam[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<StudentExam | null>(null)
  const [starting, setStarting] = useState(false)
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [resultExam, setResultExam] = useState<StudentExam | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await studentExamsApi.list(classId, page)
      setItems(result.items)
      setTotal(result.total)
    } catch (cause) {
      setError(getApiErrorMessage(cause, 'Không thể tải danh sách bài kiểm tra.'))
    } finally {
      setLoading(false)
    }
  }, [classId, page])

  useEffect(() => { void load() }, [load])

  const begin = async () => {
    if (!selected) return
    setStarting(true)
    const exam = selected
    setSelected(null)
    try {
      if (exam.require_fullscreen) {
        if (document.documentElement.requestFullscreen) {
          try { await document.documentElement.requestFullscreen() }
          catch { toast.warning('Không thể bật toàn màn hình. Bạn vẫn có thể tiếp tục làm bài.') }
        } else {
          toast.warning('Trình duyệt không hỗ trợ toàn màn hình. Bạn vẫn có thể tiếp tục làm bài.')
        }
      }
      const attempt = exam.active_attempt_id
        ? await studentExamsApi.getAttempt(exam.active_attempt_id)
        : await studentExamsApi.begin(exam.id)
      navigate(`/student/exams/${attempt.id}`)
    } catch (cause) {
      if (document.fullscreenElement) await document.exitFullscreen().catch(() => undefined)
      toast.error(getApiErrorMessage(cause, 'Không thể bắt đầu bài kiểm tra.'))
      void load()
    } finally {
      setStarting(false)
    }
  }

  if (loading) return <div className="space-y-3" aria-label="Đang tải bài kiểm tra">
    <Skeleton className="h-28 w-full" /><Skeleton className="h-28 w-full" />
  </div>

  if (error) return <Alert variant="destructive">
    <AlertCircle className="h-4 w-4" />
    <AlertTitle>Không tải được bài kiểm tra</AlertTitle>
    <AlertDescription className="mt-2 flex flex-wrap items-center justify-between gap-3">
      <span>{error}</span><Button variant="outline" size="sm" onClick={() => void load()}><RefreshCw className="mr-2 h-4 w-4" />Thử lại</Button>
    </AlertDescription>
  </Alert>

  if (!items.length) return <Card>
    <CardContent className="flex flex-col items-center gap-2 py-12 text-center">
      <BookOpenCheck className="h-8 w-8 text-muted-foreground" />
      <p className="font-medium">Chưa có bài kiểm tra được công bố</p>
      <p className="max-w-md text-sm text-muted-foreground">Bài kiểm tra sẽ xuất hiện tại đây khi giảng viên công bố cho lớp.</p>
    </CardContent>
  </Card>

  return <div className="space-y-3">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h2 className="text-sm font-medium">Bài kiểm tra đã công bố ({total})</h2>
      <Button variant="outline" size="sm" onClick={() => void load()}>
        <RefreshCw className="mr-2 h-4 w-4" />Cập nhật trạng thái
      </Button>
    </div>
    {items.map((exam) => {
      const state = labels[exam.status]
      const canStart = ['available', 'in_progress', 'retry_available'].includes(exam.status)
      return <Card key={exam.id}>
        <CardHeader className="gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div className="space-y-1">
            <CardTitle className="break-words text-base">{exam.title}</CardTitle>
            {exam.description && <CardDescription className="whitespace-pre-wrap">{exam.description}</CardDescription>}
          </div>
          <Badge variant={state.variant} className="w-fit">{state.text}</Badge>
        </CardHeader>
        <CardContent className="grid gap-2 text-sm text-muted-foreground sm:grid-cols-2 lg:grid-cols-3">
          <p className="flex items-center gap-2"><Clock3 className="h-4 w-4 shrink-0" />{exam.duration_min} phút</p>
          <p className="flex items-center gap-2"><FileQuestion className="h-4 w-4 shrink-0" />{exam.question_count} câu hỏi</p>
          <p>{localDateTime(exam.open_at)} – {localDateTime(exam.close_at)}</p>
          <p>Lượt đã dùng: {exam.used_attempts}/{exam.max_attempts}</p>
          {exam.require_fullscreen && <p className="flex items-center gap-2"><Maximize className="h-4 w-4 shrink-0" />Yêu cầu toàn màn hình</p>}
        </CardContent>
        <CardFooter className="flex-wrap justify-end gap-2 border-t pt-4">
          <Button variant="outline" onClick={() => setResultExam(exam)}>Kết quả & lượt làm</Button>
          <Button disabled={!canStart || starting} onClick={() => setSelected(exam)}>
            {exam.status === 'in_progress' ? 'Tiếp tục làm bài' : exam.status === 'retry_available' ? 'Làm lượt tiếp theo' : 'Bắt đầu làm bài'}
          </Button>
        </CardFooter>
      </Card>
    })}
    <Pagination page={page} total={total} loading={loading} onChange={setPage} />
    <Dialog open={!!resultExam} onOpenChange={open => { if (!open) setResultExam(null) }}><DialogContent className="max-h-[90dvh] max-w-3xl overflow-y-auto"><DialogHeader><DialogTitle className="break-words">Kết quả · {resultExam?.title}</DialogTitle></DialogHeader>{resultExam && <StudentExamResults examId={resultExam.id} />}</DialogContent></Dialog>
    <AlertDialog open={Boolean(selected)} onOpenChange={(open) => { if (!open && !starting) setSelected(null) }}>
      <AlertDialogContent className="max-h-[90dvh] overflow-y-auto">
        <AlertDialogHeader>
          <AlertDialogTitle>{selected?.active_attempt_id ? 'Tiếp tục bài kiểm tra?' : 'Bắt đầu bài kiểm tra?'}</AlertDialogTitle>
          <AlertDialogDescription>
            {selected?.title} · Thời lượng {selected?.duration_min} phút. Đồng hồ do máy chủ quyết định; câu trả lời được lưu khi bạn làm bài.
            {selected?.require_fullscreen && ' Bài kiểm tra yêu cầu toàn màn hình; nếu thiết bị không hỗ trợ, hệ thống sẽ báo và vẫn cho phép tiếp tục.'}
            {selected?.record_events && ` Ghi nhận ẩn tab, mất tiêu điểm, sao chép/dán, kết nối lại${selected.require_fullscreen ? ', thoát toàn màn hình' : ''}. Tính ngưỡng: ${selected.violation_types.map(type => eventLabels[type]).join(', ') || 'không có'}. ${selected.auto_submit_on_violation ? `Tự nộp khi đạt ${selected.max_violations} sự kiện tính ngưỡng.` : 'Không tự nộp theo hành vi.'} Không lưu nội dung clipboard; sự kiện không phải kết luận gian lận.`}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={starting}>Để sau</AlertDialogCancel>
          <AlertDialogAction disabled={starting} onClick={(event) => { event.preventDefault(); void begin() }}>
            {starting ? 'Đang chuẩn bị…' : 'Vào làm bài'}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  </div>
}
