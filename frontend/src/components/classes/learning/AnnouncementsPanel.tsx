import { FormEvent, useCallback, useEffect, useState } from 'react'
import dayjs from 'dayjs'
import { Plus } from 'lucide-react'
import { toast } from 'sonner'

import { Announcement, learningApi } from '@/api/learning'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'

import { getApiErrorMessage } from '@/lib/api-error'

type AnnouncementsPanelProps = {
  classId: number
  canManage: boolean
}

export function AnnouncementsPanel({ classId, canManage }: AnnouncementsPanelProps) {
  const [items, setItems] = useState<Announcement[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [open, setOpen] = useState(false)
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [pinned, setPinned] = useState(false)
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      setItems(await learningApi.announcements(classId))
    } catch (cause) {
      setError(getApiErrorMessage(cause, 'Không thể tải thông báo lớp.'))
    } finally {
      setLoading(false)
    }
  }, [classId])

  useEffect(() => {
    void load()
  }, [load])

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setSaving(true)
    try {
      await learningApi.createAnnouncement(classId, { title, content, is_pinned: pinned })
      setOpen(false)
      setTitle('')
      setContent('')
      setPinned(false)
      await load()
      toast.success('Đã đăng thông báo lớp.')
    } catch (cause) {
      toast.error(getApiErrorMessage(cause, 'Không thể đăng thông báo.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between gap-3">
        <div>
          <CardTitle className="text-base">Thông báo lớp</CardTitle>
          <CardDescription>Nội dung học tập dành riêng cho thành viên lớp.</CardDescription>
        </div>
        {canManage && (
          <Button size="sm" onClick={() => setOpen(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Đăng thông báo
          </Button>
        )}
      </CardHeader>
      <CardContent className="space-y-3">
        {loading ? (
          <>
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-24 w-full" />
          </>
        ) : error ? (
          <div className="rounded-md border border-destructive/40 p-4 text-sm">
            <p className="text-destructive">{error}</p>
            <Button className="mt-3" size="sm" variant="outline" onClick={load}>
              Thử lại
            </Button>
          </div>
        ) : items.length ? (
          items.map((item) => (
            <article className="rounded-md border p-3" key={item.id}>
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="font-medium">{item.title}</h3>
                {item.is_pinned && <Badge variant="secondary">Đã ghim</Badge>}
              </div>
              <p className="mt-2 whitespace-pre-wrap text-sm">{item.content}</p>
              <p className="mt-2 text-xs text-muted-foreground">
                {item.author_name} · {dayjs(item.created_at).format('DD/MM/YYYY HH:mm')}
              </p>
            </article>
          ))
        ) : (
          <p className="rounded-md border border-dashed py-10 text-center text-sm text-muted-foreground">
            Chưa có thông báo. Nội dung mới sẽ xuất hiện tại đây.
          </p>
        )}
      </CardContent>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <form onSubmit={submit}>
            <DialogHeader>
              <DialogTitle>Đăng thông báo lớp</DialogTitle>
              <DialogDescription>
                Thông báo sẽ gửi đến toàn bộ sinh viên đang học trong lớp.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-3 py-4">
              <div className="space-y-1.5">
                <Label htmlFor="announcement-title">Tiêu đề</Label>
                <Input
                  id="announcement-title"
                  required
                  maxLength={200}
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="announcement-content">Nội dung</Label>
                <Textarea
                  id="announcement-content"
                  required
                  maxLength={10000}
                  value={content}
                  onChange={(event) => setContent(event.target.value)}
                  rows={5}
                />
              </div>
              <label className="flex items-center gap-2 text-sm">
                <Switch checked={pinned} onCheckedChange={setPinned} />
                Ghim lên đầu danh sách
              </label>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setOpen(false)}>
                Hủy
              </Button>
              <Button type="submit" disabled={saving}>
                {saving ? 'Đang đăng…' : 'Đăng'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </Card>
  )
}
