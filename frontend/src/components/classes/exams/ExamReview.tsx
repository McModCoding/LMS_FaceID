import { useCallback, useEffect, useState } from 'react'
import { toast } from 'sonner'
import { examManagementApi, attemptStatus, scoreText, eventLabels, type ExamReview } from '@/api/exam-management'
import { RemoteState, Pagination } from '@/components/common/RemoteState'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { getApiErrorMessage } from '@/lib/api-error'

function EssayGrade({ attemptId, question, onSaved }: { attemptId: number; question: ExamReview['questions'][number]; onSaved: (data: ExamReview) => void }) {
  const [score, setScore] = useState(question.score ?? '')
  const [feedback, setFeedback] = useState(question.feedback ?? '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  return <form className="space-y-2 border-t pt-3" onSubmit={async event => {
    event.preventDefault(); setBusy(true); setError('')
    try { onSaved(await examManagementApi.grade(attemptId, question.question_id, score, feedback)); toast.success('Đã lưu điểm tự luận.') }
    catch (cause) { setError(getApiErrorMessage(cause, 'Không lưu được điểm.')) }
    finally { setBusy(false) }
  }}>
    <Label htmlFor={`grade-${question.question_id}`}>Điểm tự luận (0–{question.points})</Label>
    <Input id={`grade-${question.question_id}`} type="number" min="0" max={question.points} step="0.0001" required value={score} onChange={e => setScore(e.target.value)} />
    <Label htmlFor={`feedback-${question.question_id}`}>Nhận xét</Label>
    <Textarea id={`feedback-${question.question_id}`} maxLength={5000} value={feedback} onChange={e => setFeedback(e.target.value)} />
    {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
    <Button disabled={busy} type="submit">{busy ? 'Đang lưu…' : 'Lưu điểm tự luận'}</Button>
  </form>
}

export function ExamReviewContent({ data, canGrade = false, onSaved }: { data: ExamReview; canGrade?: boolean; onSaved?: (value: ExamReview) => void }) {
  return <div className="min-w-0 space-y-4">
    <p>{attemptStatus[data.status]} · Điểm: <strong>{scoreText(data.score10)}/10</strong>{data.is_auto_submitted ? ' · Tự động nộp' : ''}</p>
    {data.questions.map((q, index) => <section key={q.question_id} className="min-w-0 space-y-3 rounded-md border p-3">
      <h3 className="font-medium">Câu {index + 1} · {scoreText(q.score)}/{q.points} điểm</h3>
      <p className="whitespace-pre-wrap break-words">{q.content}</p>
      {q.type === 'essay' ? <p className="whitespace-pre-wrap break-words rounded-md bg-muted p-3">{q.essay_text || 'Không có câu trả lời.'}</p> : <ul className="space-y-2">{q.options.map(option => <li key={option.id} className="break-words rounded-md border p-2">
        {q.selected_option_ids?.includes(option.id) ? '☑ Đã chọn · ' : '☐ '}{option.content}{option.is_correct && <strong className="block text-sm text-success">Đáp án đúng</strong>}
      </li>)}</ul>}
      {q.explanation && <p className="whitespace-pre-wrap break-words text-sm text-muted-foreground">Giải thích: {q.explanation}</p>}
      {q.feedback && <p className="whitespace-pre-wrap break-words text-sm">Nhận xét: {q.feedback}</p>}
      {canGrade && q.type === 'essay' && data.status !== 'in_progress' && onSaved && <EssayGrade key={`${q.question_id}-${q.score}`} attemptId={data.id} question={q} onSaved={onSaved} />}
    </section>)}
  </div>
}

export function ExamAttemptReview({ attemptId, canGrade }: { attemptId: number; canGrade: boolean }) {
  const [data, setData] = useState<ExamReview | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const load = useCallback(async () => {
    setLoading(true); setError('')
    try { setData(await examManagementApi.review(attemptId)) }
    catch (cause) { setError(getApiErrorMessage(cause, 'Không tải được bài làm.')) }
    finally { setLoading(false) }
  }, [attemptId])
  useEffect(() => { void load() }, [load])
  return <><RemoteState loading={loading} error={error} onRetry={load} />{!loading && !error && data && <>
    <p className="mb-3 break-words font-medium">{data.student_code} · {data.student_name} · Lượt {data.attempt_no}</p>
    <ExamReviewContent data={data} canGrade={canGrade} onSaved={setData} />
    <ExamEventHistory attemptId={attemptId} />
  </>}</>
}

function ExamEventHistory({ attemptId }: { attemptId: number }) {
  const [data, setData] = useState<Awaited<ReturnType<typeof examManagementApi.events>> | null>(null)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const load = useCallback(async () => {
    setLoading(true); setError('')
    try { setData(await examManagementApi.events(attemptId, page)) }
    catch (cause) { setError(getApiErrorMessage(cause, 'Không tải được nhật ký.')) }
    finally { setLoading(false) }
  }, [attemptId, page])
  useEffect(() => { void load() }, [load])
  return <section className="mt-6 space-y-3 border-t pt-4"><h3 className="font-medium">Nhật ký hành vi</h3>
    <p className="text-sm text-muted-foreground">Chỉ báo cần xem xét, không kết luận gian lận. Không lưu nội dung sao chép/dán.</p>
    <RemoteState loading={loading} error={error} onRetry={load} empty={!data?.total ? 'Chưa có sự kiện được ghi nhận cho lượt này.' : undefined} />
    {!loading && !error && data && <><ul className="space-y-2 text-sm">{data.items.map(row => <li key={row.id} className="rounded-md border p-2">{eventLabels[row.type]} · {new Date(row.occurred_at).toLocaleString('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh' })}<span className="block text-muted-foreground">{row.counted ? 'Tính vào ngưỡng' : 'Chỉ ghi nhận'}</span></li>)}</ul><Pagination page={page} total={data.total} pageSize={20} loading={loading} onChange={setPage} /></>}
  </section>
}
