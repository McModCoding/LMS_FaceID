import { useEffect, useState } from 'react'
import dayjs from 'dayjs'
import { Download, Send } from 'lucide-react'
import { toast } from 'sonner'
import { Assignment, learningApi, Submission } from '@/api/learning'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { getApiErrorMessage } from '@/lib/api-error'
import { formatAssignmentDeadline } from '@/lib/assignment-time'
import { downloadBlob } from '@/lib/download'

type AssignmentDetailDialogProps = {
  assignment: Assignment | null
  canManage: boolean
  studentView: boolean
  classClosed: boolean
  submissions: Submission[]
  saving: boolean
  onClose: () => void
  onSubmitted: () => Promise<void>
  onGrade: (submission: Submission) => void
}

export function AssignmentDetailDialog({
  assignment,
  canManage,
  studentView,
  classClosed,
  submissions,
  saving,
  onClose,
  onSubmitted,
  onGrade,
}: AssignmentDetailDialogProps) {
  const [answer, setAnswer] = useState('')
  const [answerFile, setAnswerFile] = useState<File | null>(null)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    setAnswer('')
    setAnswerFile(null)
  }, [assignment?.id])

  const submit = async () => {
    if (!assignment) return
    setSubmitting(true)
    try {
      if (answerFile) {
        await learningApi.submitFile(assignment.id, answerFile, answer)
      } else {
        await learningApi.submit(assignment.id, answer)
      }
      await onSubmitted()
      toast.success(
        assignment.my_submission_id
          ? 'Đã nộp lại; điểm cũ đã được xóa.'
          : 'Đã nộp bài.',
      )
    } catch (cause) {
      toast.error(getApiErrorMessage(cause, 'Không thể nộp bài.'))
    } finally {
      setSubmitting(false)
    }
  }

  const downloadAttachment = async () => {
    if (!assignment) return
    try {
      downloadBlob(
        await learningApi.downloadAssignmentAttachment(assignment.id),
        `bai-tap-${assignment.id}`,
      )
    } catch (cause) {
      toast.error(getApiErrorMessage(cause, 'Không thể tải tệp bài tập.'))
    }
  }

  const downloadSubmission = async (submission: Submission) => {
    try {
      downloadBlob(
        await learningApi.downloadSubmission(submission.id),
        `bai-nop-${submission.id}`,
      )
    } catch (cause) {
      toast.error(getApiErrorMessage(cause, 'Không thể tải tệp bài nộp.'))
    }
  }

  return (
    <Dialog open={Boolean(assignment)} onOpenChange={(value) => !value && onClose()}>
      <DialogContent className="max-h-[85vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{assignment?.title}</DialogTitle>
          <DialogDescription>
            Hạn nộp: {assignment && formatAssignmentDeadline(assignment.due_at)} (giờ Việt Nam) · Điểm
            tối đa: {assignment?.max_score}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <p className="whitespace-pre-wrap text-sm">
            {assignment?.description || 'Không có mô tả.'}
          </p>
          {assignment?.has_attachment && (
            <Button variant="outline" size="sm" onClick={downloadAttachment}>
              <Download className="mr-2 h-4 w-4" />
              Tải tệp hướng dẫn
            </Button>
          )}

          {!studentView ? (
            <div className="space-y-2">
              <h3 className="font-medium">Bài đã nộp ({submissions.length})</h3>
              {submissions.length ? (
                submissions.map((row) => (
                  <div className="rounded-md border p-3 text-sm" key={row.id}>
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div>
                        <p className="font-medium">
                          {row.student_name} · {row.student_code}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {dayjs(row.submitted_at).format('DD/MM/YYYY HH:mm')}{' '}
                          {row.is_late ? '· Nộp trễ' : ''}
                        </p>
                      </div>
                      {canManage && <Button size="sm" variant="outline" onClick={() => onGrade(row)}>
                        Chấm bài
                      </Button>}
                    </div>
                    {row.text && <p className="mt-2 whitespace-pre-wrap">{row.text}</p>}
                    {row.has_file && (
                      <Button
                        className="mt-2"
                        size="sm"
                        variant="ghost"
                        onClick={() => downloadSubmission(row)}
                      >
                        <Download className="mr-2 h-4 w-4" />
                        Tải tệp bài nộp
                      </Button>
                    )}
                    <p className="mt-2 text-muted-foreground">
                      {row.score == null
                        ? 'Chưa chấm'
                        : `Điểm: ${row.score}/${assignment?.max_score}${
                            row.feedback ? ` · ${row.feedback}` : ''
                          }`}
                    </p>
                  </div>
                ))
              ) : (
                <p className="rounded-md border border-dashed py-8 text-center text-sm text-muted-foreground">
                  Chưa có sinh viên nộp bài.
                </p>
              )}
            </div>
          ) : (
            <div className="space-y-3">
              {assignment?.my_submission_id && (
                <div className="rounded-md border bg-muted/30 p-3 text-sm">
                  <p className="font-medium">
                    Bài đã nộp {assignment.my_is_late ? '(trễ)' : ''}
                  </p>
                  <p className="text-muted-foreground">
                    {assignment.my_score == null
                      ? 'Chưa được chấm'
                      : `Điểm: ${assignment.my_score}/${assignment.max_score}`}
                  </p>
                  {assignment.my_feedback && (
                    <p className="mt-1">Nhận xét: {assignment.my_feedback}</p>
                  )}
                  {assignment.my_score != null && (
                    <p className="mt-2 text-warning-foreground">
                      Nộp lại sẽ xóa điểm và nhận xét hiện tại.
                    </p>
                  )}
                </div>
              )}
              {classClosed || assignment?.can_submit === false ? <p className="rounded-md border p-3 text-sm text-muted-foreground">Bài tập đã kết thúc, không thể nộp bài.</p> : <>
              <div className="space-y-1.5">
                <Label htmlFor="submission-text">Nội dung bài làm</Label>
                <Textarea
                  id="submission-text"
                  value={answer}
                  onChange={(event) => setAnswer(event.target.value)}
                  rows={5}
                  placeholder="Có thể nhập nội dung hoặc chọn tệp bên dưới."
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="submission-file">Tệp bài làm</Label>
                <Input
                  id="submission-file"
                  type="file"
                  onChange={(event) => setAnswerFile(event.target.files?.[0] || null)}
                />
              </div>
              <Button
                disabled={saving || submitting || (!answer.trim() && !answerFile)}
                onClick={submit}
              >
                <Send className="mr-2 h-4 w-4" />
                {assignment?.my_submission_id ? 'Nộp lại' : 'Nộp bài'}
              </Button>
              </>}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
