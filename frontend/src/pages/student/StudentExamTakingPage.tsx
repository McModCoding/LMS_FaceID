import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { AlertCircle, Check, Clock3, LoaderCircle, Send } from 'lucide-react'
import { toast } from 'sonner'

import { studentExamsApi, type StudentExamAttempt, type StudentExamQuestion } from '@/api/student-exams'
import { getApiErrorMessage } from '@/lib/api-error'
import { ExamAnswerQueue, type SaveState } from '@/lib/exam-answer-queue'
import { useExamEvents } from '@/hooks/use-exam-events'
import { eventLabels } from '@/api/exam-management'
import { StudentExamResults } from '@/components/classes/exams/StudentExamResults'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog'

const formatRemaining = (seconds: number) => {
  const safe = Math.max(0, seconds)
  return `${String(Math.floor(safe / 3600)).padStart(2, '0')}:${String(Math.floor((safe % 3600) / 60)).padStart(2, '0')}:${String(safe % 60).padStart(2, '0')}`
}

export default function StudentExamTakingPage() {
  const { attemptId: rawAttemptId } = useParams<{ attemptId: string }>()
  const navigate = useNavigate()
  const attemptId = Number(rawAttemptId)
  const [attempt, setAttempt] = useState<StudentExamAttempt | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [serverOffset, setServerOffset] = useState(0)
  const [now, setNow] = useState(Date.now())
  const [saveState, setSaveState] = useState<SaveState>('idle')
  const [submitOpen, setSubmitOpen] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const submittingLock = useRef(false)
  const [unsavedAtClose, setUnsavedAtClose] = useState(false)
  const answerQueue = useMemo(() => new ExamAnswerQueue(
    (questionId, draft) => studentExamsApi.saveAnswer(attemptId, questionId, draft),
    setSaveState,
    (cause) => toast.error(getApiErrorMessage(cause, 'Không lưu được câu trả lời. Hãy kiểm tra kết nối và thử lưu lại.')),
  ), [attemptId])
  const autoSubmitStarted = useRef(false)
  const poll = useCallback(async () => {
    try {
      const data = await studentExamsApi.getAttempt(attemptId)
      setServerOffset(Date.parse(data.server_now) - Date.now())
      if (data.status !== 'in_progress') {
        if (answerQueue.hasPending) setUnsavedAtClose(true)
        answerQueue.clear()
      }
      setAttempt(current => current && data.status === 'in_progress' ? { ...current,
        deadline_at: data.deadline_at, server_now: data.server_now, violation_count: data.violation_count,
      } : data)
    } catch (cause) { toast.error(getApiErrorMessage(cause, 'Chưa cập nhật được trạng thái từ máy chủ. Hãy kiểm tra kết nối.')) }
  }, [attemptId, answerQueue])
  const eventError = useExamEvents(attemptId, attempt?.id === attemptId && !!attempt?.record_events && attempt.status === 'in_progress', !!attempt?.require_fullscreen, receipt => {
    setAttempt(current => current ? { ...current, violation_count: receipt.violation_count } : current)
    if (receipt.status !== 'in_progress') void poll()
  })
  useEffect(() => {
    if (attempt?.status !== 'in_progress') return
    const timer = window.setInterval(() => { void poll() }, 30000)
    window.addEventListener('online', poll)
    return () => { window.clearInterval(timer); window.removeEventListener('online', poll) }
  }, [attempt?.status, poll])

  const load = useCallback(async () => {
    if (!Number.isSafeInteger(attemptId) || attemptId <= 0) {
      setError('Đường dẫn lượt làm bài không hợp lệ.')
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const data = await studentExamsApi.getAttempt(attemptId)
      const pending = answerQueue.drafts()
      if (data.status !== 'in_progress') {
        if (answerQueue.hasPending) setUnsavedAtClose(true)
        answerQueue.clear()
      }
      setAttempt(data.status === 'in_progress' ? {
        ...data,
        questions: data.questions.map((question) => ({ ...question, ...pending.get(question.question_id) })),
      } : data)
      setServerOffset(Date.parse(data.server_now) - Date.now())

    } catch (cause) {
      setError(getApiErrorMessage(cause, 'Không thể tải lượt làm bài.'))
    } finally {
      setLoading(false)
    }
  }, [attemptId, answerQueue])

  useEffect(() => {
    autoSubmitStarted.current = false
    setUnsavedAtClose(false)
    setSaveState('idle')
    void load()
  }, [load])
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [])
  useEffect(() => {
    answerQueue.resume()
    const beforeUnload = (event: BeforeUnloadEvent) => {
      if (!answerQueue.hasPending) return
      event.preventDefault()
      event.returnValue = ''
    }
    const online = () => { void answerQueue.flush().catch(() => undefined) }
    window.addEventListener('beforeunload', beforeUnload)
    window.addEventListener('online', online)
    return () => {
      answerQueue.pause()
      window.removeEventListener('beforeunload', beforeUnload)
      window.removeEventListener('online', online)
    }
  }, [answerQueue])

  const updateQuestion = (questionId: number, update: (question: StudentExamQuestion) => StudentExamQuestion) => {
    if (!attempt || submittingLock.current) return
    const questions = attempt.questions.map((question) => {
      if (question.question_id !== questionId) return question
      const next = update(question)
      answerQueue.enqueue(questionId, next.type === 'essay'
        ? { essay_text: next.essay_text }
        : { selected_option_ids: next.selected_option_ids })
      return next
    })
    setAttempt({ ...attempt, questions })
  }

  const flushPendingAnswers = async (quietOnFailure = false) => {
    try {
      await answerQueue.flush()
      return !answerQueue.hasPending
    } catch (cause) {
      setSaveState('error')
      if (!quietOnFailure) toast.error(getApiErrorMessage(cause, 'Có câu trả lời chưa lưu được. Chưa nộp bài để tránh mất dữ liệu.'))
      return false
    }
  }

  const submit = async (dueToDeadline = false) => {
    if (!attempt || submittingLock.current) return
    submittingLock.current = true
    setSubmitting(true)
    const saved = await flushPendingAnswers(dueToDeadline)
    if (!saved && !dueToDeadline) {
      setSubmitting(false)
      submittingLock.current = false
      return
    }
    try {
      const result = await studentExamsApi.submit(attempt.id)
      if (answerQueue.hasPending) setUnsavedAtClose(true)
      answerQueue.clear()
      setAttempt(result)
      setSubmitOpen(false)
      if (document.fullscreenElement) await document.exitFullscreen().catch(() => undefined)
    } catch (cause) {
      if (!dueToDeadline) toast.error(getApiErrorMessage(cause, 'Không thể nộp bài. Hãy tải lại trạng thái lượt làm.'))
      await load()
    } finally {
      setSubmitting(false)
      submittingLock.current = false
    }
  }

  const remaining = attempt ? Math.ceil((Date.parse(attempt.deadline_at) - (now + serverOffset)) / 1000) : 0
  useEffect(() => {
    if (attempt?.status === 'in_progress' && remaining <= 0 && !autoSubmitStarted.current && !submittingLock.current) {
      autoSubmitStarted.current = true
      void submit(true)
    }
    // submit is intentionally triggered once the server-derived deadline is reached.
  }, [remaining, attempt?.status])

  if (loading) return <div className="mx-auto max-w-4xl space-y-4" aria-label="Đang tải bài làm">
    <Skeleton className="h-12 w-full" /><Skeleton className="h-24 w-full" /><Skeleton className="h-64 w-full" />
  </div>

  if (error || !attempt) return <main className="mx-auto max-w-3xl space-y-4">
    <Alert variant="destructive"><AlertCircle className="h-4 w-4" /><AlertTitle>Không mở được bài làm</AlertTitle><AlertDescription>{error || 'Không tìm thấy lượt làm bài.'}</AlertDescription></Alert>
    <Button variant="outline" onClick={() => navigate(-1)}>Quay lại</Button>
    <Button variant="secondary" onClick={() => void load()}>Thử tải lại</Button>
  </main>

  if (attempt.status !== 'in_progress') return <main className="mx-auto max-w-2xl">
    <Card>
      <CardHeader>
        <CardTitle>{attempt.is_auto_submitted ? 'Bài đã được tự động nộp' : 'Đã nộp bài'}</CardTitle>
        <CardDescription>{attempt.exam_title}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {unsavedAtClose && <Alert variant="destructive"><AlertTitle>Có câu trả lời chưa đồng bộ</AlertTitle><AlertDescription>Bài đã được chốt theo thời gian phía server. Một số thay đổi chưa lưu thành công; kết quả chỉ dùng các câu trả lời server đã nhận.</AlertDescription></Alert>}
        <p className="text-sm text-muted-foreground">Bài làm và các câu trả lời server nhận được đã được ghi nhận. Kết quả sẽ hiển thị theo quy định của bài kiểm tra.</p>
        <Button onClick={() => navigate(`/student/classes/${attempt.class_id}?tab=exams`)}>Quay lại lớp học</Button>
        <StudentExamResults examId={attempt.exam_id} />
      </CardContent>
    </Card>
  </main>

  const question = attempt.questions[selectedIndex]
  if (!question) return <main className="mx-auto max-w-3xl"><Alert variant="destructive"><AlertTitle>Đề chưa có câu hỏi</AlertTitle><AlertDescription>Hãy liên hệ giảng viên để kiểm tra lại bài kiểm tra này.</AlertDescription></Alert></main>

  return <main className="mx-auto max-w-5xl space-y-4 pb-8">
    <header className="sticky top-0 z-20 flex flex-wrap items-center justify-between gap-3 border-b bg-background/95 py-3 backdrop-blur supports-[backdrop-filter]:bg-background/80">
      <div className="min-w-0 max-w-full"><h1 className="break-words text-lg font-semibold">{attempt.exam_title}</h1><p className="text-sm text-muted-foreground">Lượt {attempt.attempt_no} · {attempt.questions.length} câu hỏi</p></div>
      <div className="flex flex-wrap items-center gap-2" aria-live="polite">
        {saveState === 'saving' && <span className="text-xs text-muted-foreground"><LoaderCircle className="mr-1 inline h-3.5 w-3.5 animate-spin" />Đang lưu</span>}
        {saveState === 'saved' && <span className="text-xs text-muted-foreground"><Check className="mr-1 inline h-3.5 w-3.5" />Đã lưu</span>}
        {saveState === 'error' && <><span className="text-xs text-destructive">Chưa lưu được</span><Button size="sm" variant="outline" disabled={submitting} onClick={() => void flushPendingAnswers()}>Thử lưu lại</Button></>}
        <span className="flex items-center gap-1 rounded-md border px-3 py-2 font-mono text-sm" aria-label={`Thời gian còn lại ${formatRemaining(remaining)}`}>
          <Clock3 className="h-4 w-4" />{formatRemaining(remaining)}
        </span>
      </div>
    </header>
    {attempt.record_events && <div className="space-y-1 rounded-md border p-3 text-xs text-muted-foreground"><p>Ghi nhận ẩn tab, mất tiêu điểm, sao chép/dán, kết nối lại{attempt.require_fullscreen ? ', thoát toàn màn hình' : ''}. Không lưu nội dung clipboard. Đây là chỉ báo cần xem xét.</p><p>Tính ngưỡng: {attempt.violation_types.map(type => eventLabels[type]).join(', ') || 'Không có'} · Đã ghi {attempt.violation_count}{attempt.max_violations ? `/${attempt.max_violations}` : ' (không giới hạn)'}. {attempt.auto_submit_on_violation ? 'Tự nộp khi đạt ngưỡng.' : 'Không tự nộp theo hành vi.'}</p><p>Giữ trang mở khi mất mạng để hệ thống thử đồng bộ lại.</p></div>}
    {eventError && <p role="alert" className="text-sm text-destructive">{eventError}</p>}

    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_220px]">
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between gap-3">
            <CardTitle className="text-base">Câu {selectedIndex + 1}</CardTitle>
            <span className="shrink-0 text-sm text-muted-foreground">{question.points} điểm</span>
          </div>
          <CardDescription className="whitespace-pre-wrap break-words text-foreground">{question.content}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {question.type === 'essay' ? <Textarea
            aria-label={`Câu trả lời câu ${selectedIndex + 1}`}
            value={question.essay_text || ''}
            disabled={submitting || remaining <= 0}
            maxLength={60000}
            onChange={(event) => updateQuestion(question.question_id, (current) => ({ ...current, essay_text: event.target.value }))}
            placeholder="Nhập câu trả lời của bạn…"
            className="min-h-48"
          /> : question.options.map((option, index) => {
            const checked = question.selected_option_ids?.includes(option.id) ?? false
            return <label key={option.id} className="flex min-h-12 cursor-pointer items-start gap-3 rounded-md border p-3 hover:bg-accent/40">
              <input
                disabled={submitting || remaining <= 0}
                type={question.type === 'multiple' ? 'checkbox' : 'radio'}
                name={`question-${question.question_id}`}
                checked={checked}
                onChange={() => updateQuestion(question.question_id, (current) => {
                  const selected = current.selected_option_ids || []
                  const next = question.type === 'multiple'
                    ? checked ? selected.filter((id) => id !== option.id) : [...selected, option.id]
                    : [option.id]
                  return { ...current, selected_option_ids: next }
                })}
                className="mt-1 h-4 w-4 accent-primary"
              />
              <span className="min-w-0 break-words text-sm"><span className="mr-2 font-medium">{String.fromCharCode(65 + index)}.</span>{option.content}</span>
            </label>
          })}
        </CardContent>
      </Card>

      <Card className="h-fit">
        <CardHeader className="pb-3"><CardTitle className="text-sm">Đi đến câu hỏi</CardTitle><CardDescription>Chọn câu để xem hoặc sửa đáp án.</CardDescription></CardHeader>
        <CardContent className="grid grid-cols-5 gap-2 lg:grid-cols-4">
          {attempt.questions.map((item, index) => {
            const answered = item.type === 'essay' ? Boolean(item.essay_text?.trim()) : Boolean(item.selected_option_ids?.length)
            return <Button key={item.question_id} className="min-h-11" type="button" variant={index === selectedIndex ? 'default' : answered ? 'secondary' : 'outline'} size="sm"
              aria-label={`Câu ${index + 1}${answered ? ', đã trả lời' : ', chưa trả lời'}`}
              aria-current={index === selectedIndex ? 'step' : undefined}
              onClick={() => setSelectedIndex(index)}>{index + 1}</Button>
          })}
        </CardContent>
      </Card>
    </div>

    <footer className="flex flex-wrap items-center justify-between gap-3">
      <p className="text-sm text-muted-foreground">Đã trả lời {attempt.questions.filter((item) => item.type === 'essay' ? Boolean(item.essay_text?.trim()) : Boolean(item.selected_option_ids?.length)).length}/{attempt.questions.length} câu</p>
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" disabled={selectedIndex === 0} onClick={() => setSelectedIndex((index) => index - 1)}>Câu trước</Button>
        {selectedIndex < attempt.questions.length - 1
          ? <Button onClick={() => setSelectedIndex((index) => index + 1)}>Câu tiếp theo</Button>
          : null}
        <Button disabled={submitting} onClick={() => setSubmitOpen(true)}><Send className="mr-2 h-4 w-4" />Nộp bài</Button>
      </div>
    </footer>

    <AlertDialog open={submitOpen} onOpenChange={setSubmitOpen}>
      <AlertDialogContent className="max-h-[90dvh] overflow-y-auto">
        <AlertDialogHeader>
          <AlertDialogTitle>Nộp bài kiểm tra?</AlertDialogTitle>
          <AlertDialogDescription>Bạn đã trả lời {attempt.questions.filter((item) => item.type === 'essay' ? Boolean(item.essay_text?.trim()) : Boolean(item.selected_option_ids?.length)).length}/{attempt.questions.length} câu. Hệ thống sẽ lưu câu trả lời đang chờ đồng bộ rồi nộp bài. Sau khi nộp, bạn không thể sửa câu trả lời.</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={submitting}>Tiếp tục làm</AlertDialogCancel>
          <AlertDialogAction disabled={submitting} onClick={(event) => { event.preventDefault(); void submit() }}>
            {submitting ? 'Đang nộp…' : 'Xác nhận nộp bài'}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  </main>
}
