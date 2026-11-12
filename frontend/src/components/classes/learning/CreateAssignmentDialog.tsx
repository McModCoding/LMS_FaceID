import { FormEvent, useState } from 'react'
import { toast } from 'sonner'
import { learningApi } from '@/api/learning'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { getApiErrorMessage } from '@/lib/api-error'
import { assignmentDeadlineToUtc } from '@/lib/assignment-time'

type CreateAssignmentDialogProps = {
  open: boolean
  saving: boolean
  onOpenChange: (open: boolean) => void
  onCreated: () => Promise<void>
  classId: number
}

export function CreateAssignmentDialog({
  open,
  saving,
  onOpenChange,
  onCreated,
  classId,
}: CreateAssignmentDialogProps) {
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [dueAt, setDueAt] = useState('')
  const [allowLate, setAllowLate] = useState(false)
  const [attachment, setAttachment] = useState<File | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [createdId, setCreatedId] = useState<number | null>(null)
  const [error, setError] = useState('')

  const create = async (event: FormEvent) => {
    event.preventDefault()
    setSubmitting(true)
    setError('')
    try {
      const id = createdId ?? (await learningApi.createAssignment(classId, {
        title,
        description: description || null,
        due_at: assignmentDeadlineToUtc(dueAt),
        max_score: 10,
        allow_late: allowLate,
        status: 'published',
      })).id
      setCreatedId(id)
      if (attachment) {
        try { await learningApi.uploadAssignmentAttachment(id, attachment) }
        catch (cause) { setError(`Bài tập đã được công bố và gửi thông báo, nhưng tệp chưa tải lên: ${getApiErrorMessage(cause, 'Lỗi kết nối hoặc tệp không hợp lệ.')} Chọn tệp khác hoặc thử lại; không tạo bài mới.`); await onCreated(); return }
      }
      setTitle('')
      setDescription('')
      setDueAt('')
      setAllowLate(false)
      setAttachment(null)
      setCreatedId(null)
      onOpenChange(false)
      await onCreated()
      toast.success('Đã giao bài tập và gửi thông báo cho sinh viên.')
    } catch (cause) {
      setError(getApiErrorMessage(cause, 'Không thể tạo bài tập.'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={value => { if (!submitting) { if (!value) { setCreatedId(null); setError(''); setTitle(''); setDescription(''); setDueAt(''); setAttachment(null); setAllowLate(false) } onOpenChange(value) } }}>
      <DialogContent>
        <form onSubmit={create}>
          <DialogHeader>
            <DialogTitle>Giao bài tập</DialogTitle>
            <DialogDescription>
              Bài tập được công bố ngay và sinh viên sẽ nhận thông báo.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-4">
            {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
            {createdId && <p className="text-sm text-muted-foreground">Đang hoàn tất tệp cho bài #{createdId}. Tiêu đề, mô tả và thời hạn đã được lưu.</p>}
            <div className="space-y-1.5">
              <Label htmlFor="assignment-title">Tiêu đề</Label>
              <Input
                id="assignment-title"
                required
                disabled={createdId !== null}
                value={title}
                onChange={(event) => setTitle(event.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="assignment-description">Mô tả</Label>
              <Textarea
                disabled={createdId !== null}
                id="assignment-description"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="assignment-due">Hạn nộp (giờ Việt Nam)</Label>
              <Input
                id="assignment-due"
                required
                type="datetime-local"
                disabled={createdId !== null}
                value={dueAt}
                onChange={(event) => setDueAt(event.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="assignment-file">Tệp hướng dẫn (không bắt buộc)</Label>
              <Input
                id="assignment-file"
                type="file"
                onChange={(event) => setAttachment(event.target.files?.[0] || null)}
              />
              <p className="text-xs text-muted-foreground">
                Tối đa 10 MB; hỗ trợ tài liệu, bảng tính, trình chiếu, ZIP, TXT và ảnh.
              </p>
            </div>
            <label className="flex items-center gap-2 text-sm">
              <Switch disabled={createdId !== null} checked={allowLate} onCheckedChange={setAllowLate} />
              Cho phép nộp trễ
            </label>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" disabled={submitting} onClick={() => { setCreatedId(null); setError(''); setTitle(''); setDescription(''); setDueAt(''); setAttachment(null); setAllowLate(false); onOpenChange(false) }}>
              {createdId ? 'Đóng, giữ bài đã công bố' : 'Hủy'}
            </Button>
            <Button type="submit" disabled={saving || submitting}>
              {saving || submitting ? 'Đang lưu…' : createdId ? attachment ? 'Thử tải lại tệp' : 'Hoàn tất không kèm tệp' : 'Công bố bài tập'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
