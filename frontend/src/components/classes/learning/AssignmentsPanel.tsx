import { useCallback, useEffect, useState } from 'react'
import { FileText, Plus } from 'lucide-react'
import { Pagination } from '@/components/common/RemoteState'
import { toast } from 'sonner'
import { Assignment, learningApi, Submission } from '@/api/learning'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { getApiErrorMessage } from '@/lib/api-error'
import { formatAssignmentDeadline } from '@/lib/assignment-time'
import { AssignmentDetailDialog } from './AssignmentDetailDialog'
import { CreateAssignmentDialog } from './CreateAssignmentDialog'
import { GradeDialog } from './GradeDialog'

type AssignmentsPanelProps = {
  classId: number
  canManage: boolean
  studentView?: boolean
  classClosed?: boolean
}

export function AssignmentsPanel({ classId, canManage, studentView = false, classClosed = false }: AssignmentsPanelProps) {
  const [items, setItems] = useState<Assignment[]>([])
  const [page, setPage] = useState(1)
  const [view, setView] = useState('all')
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [createOpen, setCreateOpen] = useState(false)
  const [detail, setDetail] = useState<Assignment | null>(null)
  const [submissions, setSubmissions] = useState<Submission[]>([])
  const [grading, setGrading] = useState<Submission | null>(null)
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const result = await learningApi.assignments(classId, page, view)
      setItems(result.items); setTotal(result.total)
    } catch (cause) {
      setError(getApiErrorMessage(cause, 'Không thể tải bài tập.'))
    } finally {
      setLoading(false)
    }
  }, [classId, page, view])

  useEffect(() => {
    void load()
  }, [load])

  const loadSubmissions = useCallback(async (assignmentId: number) => {
    setSubmissions((await learningApi.submissions(assignmentId)).items)
  }, [])

  const showDetail = async (item: Assignment) => {
    setDetail(item)
    if (studentView) return
    try {
      await loadSubmissions(item.id)
    } catch (cause) {
      toast.error(getApiErrorMessage(cause, 'Không thể tải bài nộp.'))
    }
  }

  const withSaving = async (action: () => Promise<void>) => {
    setSaving(true)
    try {
      await action()
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between gap-3">
        <div>
          <CardTitle className="text-base">Bài tập</CardTitle>
          <CardDescription>Giao bài, nộp bài và phản hồi trên cùng một luồng.</CardDescription>
        </div>
        {canManage && (
          <Button size="sm" onClick={() => setCreateOpen(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Giao bài
          </Button>
        )}
      </CardHeader>
      <CardContent className="space-y-2">
        <div className="flex flex-wrap gap-2 pb-3" aria-label="Lọc bài tập">{(studentView ? [['all', 'Tất cả'], ['todo', 'Cần thực hiện'], ['submitted', 'Đã nộp'], ['finished', 'Đã kết thúc']] : [['all', 'Tất cả'], ['pending', 'Chờ chấm'], ['finished', 'Đã kết thúc']]).map(([key, label]) => <Button type="button" key={key} size="sm" variant={view === key ? 'secondary' : 'outline'} aria-pressed={view === key} onClick={() => { setView(key); setPage(1) }}>{label}</Button>)}</div>
        {loading ? (
          <>
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-16 w-full" />
          </>
        ) : error ? (
          <div className="rounded-md border border-destructive/40 p-4 text-sm">
            <p className="text-destructive">{error}</p>
            <Button className="mt-3" size="sm" variant="outline" onClick={load}>
              Thử lại
            </Button>
          </div>
        ) : items.length ? (
          <><div className="divide-y">{items.map((item) => (
            <button key={item.id} onClick={() => showDetail(item)} className="grid w-full grid-cols-[auto_minmax(0,1fr)] items-start gap-x-3 gap-y-2 py-4 text-left hover:bg-accent/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring sm:grid-cols-[auto_minmax(0,1fr)_auto_auto] sm:items-center">
              <span className="rounded-lg bg-secondary p-2 text-primary"><FileText className="h-5 w-5" /></span>
              <span className="min-w-0 flex-1"><span className="block break-words font-medium">{item.title}</span><span className="block text-sm text-muted-foreground">Hạn: {formatAssignmentDeadline(item.due_at)} (giờ Việt Nam) · Thang điểm {item.max_score}</span></span>
              <Badge className="col-start-2 w-fit sm:col-auto" variant={item.my_submission_id ? 'success' : 'secondary'}>{!studentView ? item.status === 'draft' ? 'Nháp' : item.pending_count ? `${item.pending_count} bài chờ chấm` : 'Đã công bố' : item.my_submission_id ? item.my_is_late ? 'Đã nộp trễ' : 'Đã nộp' : classClosed || item.availability === 'closed' ? 'Đã kết thúc' : item.availability === 'late_allowed' ? 'Còn nhận bài trễ' : 'Chưa nộp'}</Badge>
              <span className="col-start-2 text-sm font-medium text-primary sm:col-auto">Xem bài</span>
            </button>
          ))}</div><Pagination page={page} total={total} pageSize={20} loading={loading} onChange={setPage} /></>
        ) : (
          <p className="rounded-md border border-dashed py-10 text-center text-sm text-muted-foreground">
            {view !== 'all' ? 'Không có bài tập phù hợp. Hãy đổi bộ lọc.' : canManage ? 'Chưa có bài tập. Hãy giao bài đầu tiên cho lớp.' : 'Chưa có bài tập. Bài tập mới sẽ xuất hiện tại đây.'}
          </p>
        )}
      </CardContent>

      <CreateAssignmentDialog
        open={createOpen}
        saving={saving}
        onOpenChange={setCreateOpen}
        classId={classId}
        onCreated={() => withSaving(load)}
      />
      <AssignmentDetailDialog
        assignment={detail}
        canManage={canManage}
        studentView={studentView}
        classClosed={classClosed}
        submissions={submissions}
        saving={saving}
        onClose={() => setDetail(null)}
        onSubmitted={() =>
          withSaving(async () => {
            await load()
            setDetail(null)
          })
        }
        onGrade={setGrading}
      />
      <GradeDialog
        assignment={detail}
        submission={grading}
        saving={saving}
        onClose={() => setGrading(null)}
        onSaved={() =>
          withSaving(async () => {
            setGrading(null)
            if (detail) await loadSubmissions(detail.id)
          })
        }
      />
    </Card>
  )
}
