import { FormEvent, useCallback, useEffect, useState } from 'react'
import { toast } from 'sonner'
import { Material, materialsApi } from '@/api/materials'
import { getApiErrorMessage } from '@/lib/api-error'
import { downloadBlob } from '@/lib/download'
import { Pagination, RemoteState } from '@/components/common/RemoteState'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog'

export function MaterialsPanel({ classId, canManage = false }: { classId: number; canManage?: boolean }) {
  const [data, setData] = useState<{ items: Material[]; total: number }>({ items: [], total: 0 })
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<Material | null>(null)
  const [deleting, setDeleting] = useState<Material | null>(null)
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [kind, setKind] = useState<'file' | 'link'>('link')
  const [url, setUrl] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [formError, setFormError] = useState('')
  const load = useCallback(async () => {
    setLoading(true); setError('')
    try { setData(await materialsApi.list(classId, page)) }
    catch (cause) { setError(getApiErrorMessage(cause, 'Không thể tải học liệu.')) }
    finally { setLoading(false) }
  }, [classId, page])
  useEffect(() => { void load() }, [load])
  const showForm = (item: Material | null) => { setEditing(item); setTitle(item?.title ?? ''); setDescription(item?.description ?? ''); setKind('link'); setUrl(''); setFile(null); setFormError(''); setOpen(true) }
  const save = async (event: FormEvent) => {
    event.preventDefault(); setBusy(true); setFormError('')
    try {
      if (editing) await materialsApi.update(editing.id, title.trim(), description.trim())
      else {
        const form = new FormData(); form.append('title', title.trim()); form.append('description', description.trim())
        if (kind === 'link') form.append('url', url.trim())
        else if (file) form.append('file', file)
        await materialsApi.create(classId, form)
      }
      setOpen(false); toast.success('Đã lưu học liệu.'); await load()
    } catch (cause) { setFormError(getApiErrorMessage(cause, 'Không thể lưu học liệu.')) }
    finally { setBusy(false) }
  }
  const remove = async () => {
    if (!deleting) return
    setBusy(true)
    try { await materialsApi.remove(deleting.id); setDeleting(null); toast.success('Đã xóa học liệu.'); if (data.items.length === 1 && page > 1) setPage(page - 1); else await load() }
    catch (cause) { toast.error(getApiErrorMessage(cause, 'Không thể xóa học liệu.')) }
    finally { setBusy(false) }
  }
  const download = async (item: Material) => {
    try { downloadBlob(await materialsApi.download(item.id), item.filename || 'hoc-lieu') }
    catch (cause) { toast.error(getApiErrorMessage(cause, 'Không thể tải tệp học liệu.')) }
  }
  return <Card><CardHeader><div className="flex flex-wrap items-center justify-between gap-3"><CardTitle className="text-base">Học liệu</CardTitle>{canManage && <Button onClick={() => showForm(null)}>Thêm học liệu</Button>}</div><CardDescription>Tài liệu và liên kết phục vụ lớp học. Liên kết ngoài mở ở tab mới.</CardDescription></CardHeader><CardContent className="space-y-4">
    {loading || error || !data.items.length ? <RemoteState loading={loading} error={error} empty={canManage ? 'Chưa có học liệu. Chọn Thêm học liệu để đăng tài liệu hoặc liên kết.' : 'Chưa có học liệu. Giảng viên sẽ đăng tài liệu cho lớp tại đây.'} onRetry={load} /> : data.items.map(item => <article className="space-y-2 rounded-md border p-4 text-sm" key={item.id}><h3 className="break-words font-medium">{item.title}</h3>{item.description && <p className="whitespace-pre-wrap break-words text-muted-foreground">{item.description}</p>}<div className="flex flex-wrap gap-2">{item.url ? <Button asChild size="sm" variant="outline"><a href={item.url} target="_blank" rel="noopener noreferrer">Mở liên kết</a></Button> : <Button size="sm" variant="outline" onClick={() => download(item)}>Tải {item.filename}</Button>}{canManage && <><Button size="sm" variant="outline" onClick={() => showForm(item)}>Sửa mô tả</Button><Button size="sm" variant="outline" onClick={() => setDeleting(item)}>Xóa học liệu</Button></>}</div></article>)}
    <Pagination page={page} total={data.total} loading={loading} onChange={setPage} />
    <Dialog open={open} onOpenChange={value => !busy && setOpen(value)}><DialogContent className="max-h-[85vh] overflow-y-auto"><DialogHeader><DialogTitle>{editing ? 'Sửa học liệu' : 'Thêm học liệu'}</DialogTitle><DialogDescription>{editing ? 'Sửa tiêu đề và mô tả. Muốn thay tệp hoặc liên kết, tạo học liệu mới rồi xóa mục cũ.' : 'Học liệu được hiển thị ngay cho sinh viên trong lớp sau khi lưu.'}</DialogDescription></DialogHeader><form className="space-y-4" onSubmit={save}><div className="space-y-2"><Label htmlFor="material-title">Tiêu đề học liệu</Label><Input id="material-title" required maxLength={200} value={title} onChange={event => setTitle(event.target.value)} /></div><div className="space-y-2"><Label htmlFor="material-description">Mô tả học liệu</Label><Textarea id="material-description" maxLength={5000} value={description} onChange={event => setDescription(event.target.value)} /></div>{!editing && <><fieldset className="flex gap-4"><legend className="mb-2 text-sm font-medium">Loại học liệu</legend><label className="flex items-center gap-2 text-sm"><input type="radio" name="material-kind" checked={kind === 'link'} onChange={() => setKind('link')} />Liên kết HTTPS</label><label className="flex items-center gap-2 text-sm"><input type="radio" name="material-kind" checked={kind === 'file'} onChange={() => setKind('file')} />Tệp tài liệu</label></fieldset>{kind === 'link' ? <div className="space-y-2"><Label htmlFor="material-url">Liên kết HTTPS</Label><Input id="material-url" type="url" required value={url} onChange={event => setUrl(event.target.value)} placeholder="https://…" /></div> : <div className="space-y-2"><Label htmlFor="material-file">Tệp học liệu</Label><Input id="material-file" type="file" required onChange={event => setFile(event.target.files?.[0] ?? null)} /><p className="text-xs text-muted-foreground">Tối đa 10 MB theo cấu hình mặc định. Hỗ trợ tài liệu Office, PDF, TXT, ZIP và ảnh; server kiểm tra nội dung thực.</p></div>}</>}{formError && <p role="alert" className="text-sm text-destructive">{formError}</p>}<Button type="submit" disabled={busy || !title.trim()}>{busy ? 'Đang lưu…' : 'Lưu học liệu'}</Button></form></DialogContent></Dialog>
    <AlertDialog open={!!deleting} onOpenChange={value => !value && !busy && setDeleting(null)}><AlertDialogContent><AlertDialogHeader><AlertDialogTitle>Xóa học liệu?</AlertDialogTitle><AlertDialogDescription>“{deleting?.title}” sẽ không còn trong lớp. Tệp đính kèm được dọn sau khi xóa bản ghi.</AlertDialogDescription></AlertDialogHeader><AlertDialogFooter><AlertDialogCancel disabled={busy}>Quay lại</AlertDialogCancel><AlertDialogAction disabled={busy} onClick={event => { event.preventDefault(); void remove() }}>{busy ? 'Đang xóa…' : 'Xác nhận xóa'}</AlertDialogAction></AlertDialogFooter></AlertDialogContent></AlertDialog>
  </CardContent></Card>
}
