import { useCallback, useEffect, useState } from 'react'
import { toast } from 'sonner'
import { examManagementApi, attemptStatus, scoreText, type ExamStatistics, type ExamAttemptSummary } from '@/api/exam-management'
import { RemoteState, Pagination } from '@/components/common/RemoteState'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { getApiErrorMessage } from '@/lib/api-error'
import { ExamAttemptReview } from './ExamReview'

export function ExamManagement({ examId, canGrade }: { examId: number; canGrade: boolean }) {
  const [stats, setStats] = useState<ExamStatistics | null>(null)
  const [attempts, setAttempts] = useState<ExamAttemptSummary[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [state, setState] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [reviewId, setReviewId] = useState<number | null>(null)
  const [exporting, setExporting] = useState(false)
  const load = useCallback(async () => {
    setLoading(true); setError('')
    try {
      const [summary, list] = await Promise.all([examManagementApi.stats(examId), examManagementApi.attempts(examId, page, state)])
      setStats(summary); setAttempts(list.items); setTotal(list.total)
    } catch (cause) { setError(getApiErrorMessage(cause, 'Không tải được thống kê và bài làm.')) }
    finally { setLoading(false) }
  }, [examId, page, state])
  useEffect(() => { void load() }, [load])
  return <div className="min-w-0 space-y-5">
    <div className="flex flex-wrap gap-2"><Button variant="outline" onClick={() => void load()}>Cập nhật</Button><Button disabled={exporting || loading || !!error} onClick={async () => {
      setExporting(true)
      try {
        const blob = await examManagementApi.export(examId)
        const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = `ket-qua-kiem-tra-${examId}.xlsx`; a.click(); URL.revokeObjectURL(url)
      } catch (cause) { toast.error(getApiErrorMessage(cause, 'Không xuất được kết quả.')) }
      finally { setExporting(false) }
    }}>{exporting ? 'Đang xuất…' : 'Xuất Excel'}</Button></div>
    <RemoteState loading={loading} error={error} onRetry={load} />
    {!loading && !error && stats && <>
      <section aria-label="Thống kê bài kiểm tra" className="space-y-3">
        <h3 className="font-medium">Điểm theo {stats.score_policy === 'highest' ? 'lượt cao nhất' : 'lượt cuối'} · thang 10</h3>
        <dl className="grid grid-cols-2 gap-3 rounded-md border p-3 sm:grid-cols-3">
          {[["Đang làm", stats.in_progress], ["Lượt đã nộp", stats.submitted], ["Lượt chờ chấm", stats.pending_grading], ["SV có điểm hoàn tất", stats.graded_students], ["Trung bình", scoreText(stats.average)], ["Cao / thấp nhất", `${scoreText(stats.highest)} / ${scoreText(stats.lowest)}`]].map(([label, value]) => <div key={label}><dt className="text-xs text-muted-foreground">{label}</dt><dd className="text-lg font-medium">{value}</dd></div>)}
        </dl>
        <p className="text-xs text-muted-foreground">Chỉ tính điểm chọn khi mọi lượt đã bắt đầu của sinh viên được chấm xong. Tỷ lệ câu đúng tính trên các lượt đã nộp, theo đáp án đóng băng.</p>
        <h4 className="text-sm font-medium">Phổ điểm</h4>
        <ul aria-label="Phổ điểm" className="space-y-1">{stats.histogram.map(bin => <li key={bin.label} className="grid grid-cols-[3rem_minmax(0,1fr)_2rem] items-center gap-2 text-xs"><span>{bin.label}</span><div className="h-3 rounded bg-muted"><div className="h-3 rounded bg-primary" style={{ width: `${100 * bin.count / Math.max(1, ...stats.histogram.map(b => b.count))}%` }} /></div><span>{bin.count}</span></li>)}</ul>
        <details className="rounded-md border p-3"><summary className="cursor-pointer text-sm font-medium">Tỷ lệ đúng theo câu ({stats.questions.length})</summary><ul className="mt-3 space-y-3 text-sm">{stats.questions.map((q, index) => <li key={q.question_id} className="break-words">Câu {index + 1}: {q.content}<span className="block text-muted-foreground">{q.type === 'essay' ? 'Tự luận · chấm tay' : `Đúng hoàn toàn: ${q.correct}/${q.total} (${q.correct_rate === null ? 'chưa có' : `${(100 * Number(q.correct_rate)).toFixed(1)}%`})`}</span></li>)}</ul></details>
        <details className="rounded-md border p-3"><summary className="cursor-pointer text-sm font-medium">Sinh viên chưa làm ({stats.not_started.length})</summary><ul className="mt-3 space-y-1 text-sm">{stats.not_started.map(s => <li key={s.student_id} className="break-words">{s.student_code} · {s.student_name}</li>)}</ul>{!stats.not_started.length && <p className="mt-2 text-sm">Tất cả sinh viên đang ghi danh đã bắt đầu.</p>}</details>
      </section>
      <section className="space-y-3"><h3 className="font-medium">Danh sách lượt làm</h3>
        <Label htmlFor="attempt-state">Lọc trạng thái</Label><select id="attempt-state" className="h-10 w-full rounded-md border bg-background px-3 text-sm" value={state} onChange={e => { setPage(1); setState(e.target.value) }}><option value="">Tất cả</option><option value="in_progress">Đang làm</option><option value="pending_grading">Chờ chấm tự luận</option><option value="graded">Đã chấm</option></select>
        {!attempts.length && <p className="text-sm text-muted-foreground">Chưa có lượt phù hợp. Đổi bộ lọc hoặc chờ sinh viên làm bài.</p>}
        {attempts.map(a => <div key={a.id} className="flex flex-wrap items-center justify-between gap-3 rounded-md border p-3"><div className="min-w-0 break-words"><p className="font-medium">{a.student_code} · {a.student_name}</p><p className="text-sm">Lượt {a.attempt_no} · {attemptStatus[a.status]}</p><p className="text-sm text-muted-foreground">{scoreText(a.score10)}/10 · {a.violation_count} sự kiện tính ngưỡng{a.is_auto_submitted && ' · Tự nộp'}</p></div><Button variant="outline" onClick={() => setReviewId(a.id)}>Xem / chấm bài</Button></div>)}
        <Pagination page={page} total={total} pageSize={20} loading={loading} onChange={setPage} />
      </section>
    </>}
    <Dialog open={reviewId !== null} onOpenChange={open => { if (!open) { setReviewId(null); void load() } }}><DialogContent className="max-h-[90dvh] max-w-3xl overflow-y-auto"><DialogHeader><DialogTitle>Bài làm và chấm tự luận</DialogTitle></DialogHeader>{reviewId && <ExamAttemptReview attemptId={reviewId} canGrade={canGrade} />}</DialogContent></Dialog>
  </div>
}
