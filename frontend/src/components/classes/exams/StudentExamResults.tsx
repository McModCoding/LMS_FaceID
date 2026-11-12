import { useCallback, useEffect, useState } from 'react'
import { examManagementApi, attemptStatus, scoreText, type ExamResults, type ExamReview } from '@/api/exam-management'
import { RemoteState } from '@/components/common/RemoteState'
import { Button } from '@/components/ui/button'
import { getApiErrorMessage } from '@/lib/api-error'
import { ExamReviewContent } from './ExamReview'

export function StudentExamResults({ examId }: { examId: number }) {
  const [data, setData] = useState<ExamResults | null>(null)
  const [detail, setDetail] = useState<ExamReview | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [detailError, setDetailError] = useState('')
  const load = useCallback(async () => {
    setLoading(true); setError('')
    try { setData(await examManagementApi.results(examId)) }
    catch (cause) { setError(getApiErrorMessage(cause, 'Không tải được kết quả.')) }
    finally { setLoading(false) }
  }, [examId])
  useEffect(() => { void load() }, [load])
  return <div className="space-y-4"><RemoteState loading={loading} error={error} onRetry={load} />
    {!loading && !error && data && <>
      <p className="text-sm">{data.reason}</p>
      {data.available && <p>Điểm được chọn ({data.score_policy === 'highest' ? 'cao nhất' : 'lượt cuối'}): <strong>{scoreText(data.score10)}/10</strong>{data.score10 === null && ' · Chưa có điểm hoàn tất cho tất cả lượt.'}</p>}
      {!data.attempts.length && <p className="text-sm text-muted-foreground">Bạn chưa làm bài kiểm tra này. Quay về danh sách để bắt đầu trong khung giờ cho phép.</p>}
      {data.attempts.map(a => <div key={a.id} className="flex flex-wrap items-center justify-between gap-2 rounded-md border p-3">
        <p>Lượt {a.attempt_no} · {attemptStatus[a.status]}{a.is_auto_submitted && ' · Tự nộp'}{data.available && <span className="block text-sm">Điểm: {scoreText(a.score10)}/10</span>}</p>
        {data.available && a.status !== 'in_progress' && <Button variant="outline" disabled={busy} onClick={async () => {
          setBusy(true); setDetailError('')
          try { setDetail(await examManagementApi.result(a.id)) }
          catch (cause) { setDetailError(getApiErrorMessage(cause, 'Không xem được bài làm.')) }
          finally { setBusy(false) }
        }}>Xem bài làm lượt {a.attempt_no}</Button>}
      </div>)}
      {busy && <RemoteState loading />}{detailError && <p role="alert" className="text-destructive">{detailError}</p>}
      {detail && <section className="space-y-3 border-t pt-4"><h3 className="font-medium">Chi tiết lượt {detail.attempt_no}</h3><ExamReviewContent data={detail} /></section>}
    </>}
  </div>
}
