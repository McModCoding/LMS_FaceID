import { FormEvent, useEffect, useState } from 'react'
import { toast } from 'sonner'
import { Assignment, learningApi, Submission } from '@/api/learning'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { getApiErrorMessage } from '@/lib/api-error'

type GradeDialogProps = {
  assignment: Assignment | null
  submission: Submission | null
  saving: boolean
  onClose: () => void
  onSaved: () => Promise<void>
}

export function GradeDialog({ assignment, submission, saving, onClose, onSaved }: GradeDialogProps) {
  const [score, setScore] = useState('')
  const [feedback, setFeedback] = useState('')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    setScore(submission?.score?.toString() || '')
    setFeedback(submission?.feedback || '')
  }, [submission])

  const grade = async (event: FormEvent) => {
    event.preventDefault()
    if (!submission) return
    setSubmitting(true)
    try {
      await learningApi.grade(submission.id, Number(score), feedback || undefined)
      await onSaved()
      toast.success('Đã lưu điểm và gửi thông báo cho sinh viên.')
    } catch (cause) {
      toast.error(getApiErrorMessage(cause, 'Không thể chấm bài.'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={Boolean(submission)} onOpenChange={(value) => !value && onClose()}>
      <DialogContent>
        <form onSubmit={grade}>
          <DialogHeader>
            <DialogTitle>Chấm bài của {submission?.student_name}</DialogTitle>
            <DialogDescription>
              Điểm phải nằm trong khoảng 0–{assignment?.max_score}. Sinh viên sẽ nhận thông báo
              sau khi lưu.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-4">
            <div className="space-y-1.5">
              <Label htmlFor="submission-score">Điểm</Label>
              <Input
                id="submission-score"
                required
                type="number"
                min="0"
                max={assignment?.max_score}
                step="0.1"
                value={score}
                onChange={(event) => setScore(event.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="submission-feedback">Nhận xét</Label>
              <Textarea
                id="submission-feedback"
                maxLength={5000}
                value={feedback}
                onChange={(event) => setFeedback(event.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              Hủy
            </Button>
            <Button type="submit" disabled={saving || submitting}>
              Lưu điểm
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
