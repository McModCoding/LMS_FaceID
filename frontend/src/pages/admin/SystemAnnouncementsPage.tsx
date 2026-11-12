import { FormEvent, useCallback, useEffect, useState } from 'react'
import dayjs from 'dayjs'
import { Bell, Plus } from 'lucide-react'
import { toast } from 'sonner'
import { Announcement, learningApi } from '@/api/learning'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'

const errorText = (error: unknown, fallback: string) => {
  const data = (error as { response?: { data?: { error?: { message?: string }; detail?: { message?: string } } } }).response?.data
  return data?.error?.message || data?.detail?.message || fallback
}

export default function SystemAnnouncementsPage() {
  const [items, setItems] = useState<Announcement[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [open, setOpen] = useState(false)
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [pinned, setPinned] = useState(false)

  const load = useCallback(async () => {
    setLoading(true); setError('')
    try { setItems(await learningApi.systemAnnouncements()) }
    catch (cause) { setError(errorText(cause, 'Không thể tải thông báo hệ thống.')) }
    finally { setLoading(false) }
  }, [])
  useEffect(() => { load() }, [load])

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    try {
      await learningApi.createSystemAnnouncement({ title, content, is_pinned: pinned })
      setOpen(false); setTitle(''); setContent(''); setPinned(false)
      await load(); toast.success('Đã gửi thông báo đến người dùng đang hoạt động.')
    } catch (cause) { toast.error(errorText(cause, 'Không thể gửi thông báo hệ thống.')) }
  }

  return <div className="space-y-5"><div className="flex flex-wrap items-start justify-between gap-3"><div><h1 className="text-2xl font-semibold">Thông báo hệ thống</h1><p className="mt-1 text-sm text-muted-foreground">Thông tin vận hành gửi đến mọi tài khoản đang hoạt động.</p></div><Button onClick={() => setOpen(true)}><Plus className="mr-2 h-4 w-4" />Tạo thông báo</Button></div><Card><CardHeader><CardTitle className="flex items-center gap-2 text-base"><Bell className="h-4 w-4 text-primary" />Thông báo đã đăng</CardTitle><CardDescription>Thông báo lớp được quản lý trong từng lớp học phần.</CardDescription></CardHeader><CardContent className="space-y-3">{loading ? <><Skeleton className="h-24 w-full" /><Skeleton className="h-24 w-full" /></> : error ? <div className="rounded-md border border-destructive/40 p-4 text-sm"><p className="text-destructive">{error}</p><Button className="mt-3" size="sm" variant="outline" onClick={load}>Thử lại</Button></div> : items.length ? items.map(item => <article className="rounded-md border p-4" key={item.id}><div className="flex flex-wrap items-center gap-2"><h2 className="font-medium">{item.title}</h2>{item.is_pinned && <Badge variant="secondary">Đã ghim</Badge>}</div><p className="mt-2 whitespace-pre-wrap text-sm">{item.content}</p><p className="mt-2 text-xs text-muted-foreground">{item.author_name} · {dayjs(item.created_at).format('DD/MM/YYYY HH:mm')}</p></article>) : <p className="rounded-md border border-dashed py-12 text-center text-sm text-muted-foreground">Chưa có thông báo hệ thống. Chỉ tạo khi có thông tin vận hành cần gửi đến mọi người dùng.</p>}</CardContent></Card><Dialog open={open} onOpenChange={setOpen}><DialogContent><form onSubmit={submit}><DialogHeader><DialogTitle>Tạo thông báo hệ thống</DialogTitle><DialogDescription>Nội dung sẽ tạo thông báo trong ứng dụng cho mọi tài khoản đang hoạt động, trừ tài khoản của bạn.</DialogDescription></DialogHeader><div className="space-y-3 py-4"><div className="space-y-1.5"><Label htmlFor="system-title">Tiêu đề</Label><Input id="system-title" required maxLength={200} value={title} onChange={event => setTitle(event.target.value)} /></div><div className="space-y-1.5"><Label htmlFor="system-content">Nội dung</Label><Textarea id="system-content" required maxLength={10000} rows={6} value={content} onChange={event => setContent(event.target.value)} /></div><label className="flex items-center gap-2 text-sm"><Switch checked={pinned} onCheckedChange={setPinned} />Ghim trong danh sách quản trị</label></div><DialogFooter><Button type="button" variant="outline" onClick={() => setOpen(false)}>Hủy</Button><Button type="submit">Gửi thông báo</Button></DialogFooter></form></DialogContent></Dialog></div>
}
