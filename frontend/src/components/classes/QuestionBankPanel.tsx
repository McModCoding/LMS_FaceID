import { useCallback, useEffect, useState } from 'react'
import { toast } from 'sonner'
import { questionsApi, type Difficulty, type ImportPreview, type Question, type QuestionInput, type QuestionType } from '@/api/questions'
import { getApiErrorMessage } from '@/lib/api-error'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'

const types: Record<QuestionType, string> = { single: 'Một đáp án', multiple: 'Nhiều đáp án', true_false: 'Đúng / Sai', essay: 'Tự luận' }
const difficulties: Record<Difficulty, string> = { easy: 'Dễ', medium: 'Trung bình', hard: 'Khó' }
const emptyOptions = () => [{ content: '', is_correct: false }, { content: '', is_correct: false }]
const emptyForm = (): QuestionInput => ({ type: 'single', content: '', difficulty: 'medium', explanation: null, options: emptyOptions() })

function questionError(error: unknown, fallback: string) {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (Array.isArray(detail)) {
    const messages = detail.map(item => typeof item?.msg === 'string' ? item.msg.replace(/^Value error, /, '') : '').filter(Boolean)
    if (messages.length) return messages.join('; ')
  }
  return getApiErrorMessage(error, fallback)
}

export function QuestionBankPanel({ subjectId, subjectName }: { subjectId: number; subjectName?: string | null }) {
  const [items, setItems] = useState<Question[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [filterType, setFilterType] = useState('all')
  const [filterDifficulty, setFilterDifficulty] = useState('all')
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [form, setForm] = useState<QuestionInput>(emptyForm)
  const [editing, setEditing] = useState<Question | null>(null)
  const [formOpen, setFormOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState<Question | null>(null)
  const [preview, setPreview] = useState<ImportPreview | null>(null)
  const [importOpen, setImportOpen] = useState(false)
  const [importing, setImporting] = useState(false)

  const load = useCallback(async () => {
    setLoading(true); setLoadError('')
    try {
      const data = await questionsApi.list(subjectId, { page, page_size: 20, search, ...(filterType !== 'all' && { question_type: filterType }), ...(filterDifficulty !== 'all' && { difficulty: filterDifficulty }) })
      setItems(data.items); setTotal(data.total)
    } catch (error) { setLoadError(getApiErrorMessage(error, 'Không thể tải ngân hàng câu hỏi.')) }
    finally { setLoading(false) }
  }, [subjectId, page, search, filterType, filterDifficulty])
  useEffect(() => { void load() }, [load])

  function setType(type: QuestionType) {
    setForm(current => ({ ...current, type, options: type === 'essay' ? [] : type === 'true_false' ? [{ content: 'Đúng', is_correct: false }, { content: 'Sai', is_correct: false }] : emptyOptions() }))
  }
  async function save(event: React.FormEvent) {
    event.preventDefault(); setSaving(true)
    try {
      if (editing) await questionsApi.update(editing.id, form)
      else await questionsApi.create(subjectId, form)
      toast.success('Đã lưu câu hỏi.'); setFormOpen(false); await load()
    } catch (error) { toast.error(questionError(error, 'Không thể lưu câu hỏi. Kiểm tra nội dung và đáp án.')) }
    finally { setSaving(false) }
  }
  async function downloadTemplate() {
    try {
      const blob = await questionsApi.template(subjectId)
      const url = URL.createObjectURL(blob); const link = document.createElement('a')
      link.href = url; link.download = 'mau-cau-hoi.xlsx'; link.click(); URL.revokeObjectURL(url)
    } catch (error) { toast.error(getApiErrorMessage(error, 'Không thể tải mẫu.')) }
  }
  async function upload(file: File | undefined) {
    setPreview(null)
    if (!file) return
    setImporting(true)
    try { setPreview(await questionsApi.preview(subjectId, file)) }
    catch (error) { toast.error(getApiErrorMessage(error, 'Không thể đọc tệp.')) }
    finally { setImporting(false) }
  }
  async function confirmImport() {
    if (!preview?.valid.length) return
    setImporting(true)
    try {
      const result = await questionsApi.confirm(subjectId, preview.valid.map(row => row.item))
      toast.success(`Đã nhập ${result.created} câu hỏi.`); setImportOpen(false); setPreview(null); await load()
    } catch (error) { toast.error(getApiErrorMessage(error, 'Không thể nhập câu hỏi.')) }
    finally { setImporting(false) }
  }
  return <Card><CardHeader><CardTitle>Ngân hàng câu hỏi · {subjectName || 'Môn học'}</CardTitle><p className="text-sm text-muted-foreground">Dùng chung theo môn học. Giảng viên chỉ sửa hoặc xóa câu hỏi do mình tạo.</p></CardHeader>
    <CardContent className="space-y-4">
      <div className="flex flex-wrap gap-2"><Button onClick={() => { setEditing(null); setForm(emptyForm()); setFormOpen(true) }}>Thêm câu hỏi</Button><Button variant="outline" onClick={() => { setPreview(null); setImportOpen(true) }}>Nhập Excel</Button></div>
      <div className="grid gap-2 md:grid-cols-3"><Input aria-label="Tìm câu hỏi" placeholder="Tìm nội dung câu hỏi" value={search} onChange={e => { setSearch(e.target.value); setPage(1) }} />
        <Select value={filterType} onValueChange={value => { setFilterType(value); setPage(1) }}><SelectTrigger aria-label="Lọc loại câu hỏi"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="all">Tất cả loại</SelectItem>{Object.entries(types).map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}</SelectContent></Select>
        <Select value={filterDifficulty} onValueChange={value => { setFilterDifficulty(value); setPage(1) }}><SelectTrigger aria-label="Lọc độ khó"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="all">Tất cả độ khó</SelectItem>{Object.entries(difficulties).map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}</SelectContent></Select>
      </div>
      {loading ? <div className="space-y-2"><Skeleton className="h-16 w-full" /><Skeleton className="h-16 w-full" /></div> : loadError ? <div role="alert"><p>{loadError}</p><Button variant="outline" onClick={() => void load()}>Thử lại</Button></div> : items.length === 0 ? <p className="py-6 text-muted-foreground">Không có câu hỏi phù hợp. Hãy thêm câu hỏi hoặc thay đổi bộ lọc.</p> : <div className="space-y-3">{items.map(item => <div key={item.id} className="rounded-md border p-4 space-y-2"><p className="whitespace-pre-wrap break-words font-medium">{item.content}</p><p className="text-sm text-muted-foreground">{types[item.type]} · {difficulties[item.difficulty]}</p>{item.options.length > 0 && <ul className="text-sm space-y-1">{item.options.map((option, index) => <li key={index} className="break-words">{String.fromCharCode(65 + index)}. {option.content}{option.is_correct ? ' — Đáp án đúng' : ''}</li>)}</ul>}{item.explanation && <p className="text-sm break-words">Giải thích: {item.explanation}</p>}{item.can_edit && <div className="flex gap-2"><Button variant="outline" size="sm" onClick={() => { setEditing(item); setForm({ type: item.type, content: item.content, difficulty: item.difficulty, explanation: item.explanation, options: item.options.map(o => ({ content: o.content, is_correct: o.is_correct })) }); setFormOpen(true) }}>Sửa</Button><Button variant="outline" size="sm" onClick={() => setDeleting(item)}>Xóa</Button></div>}</div>)}</div>}
      <div className="flex flex-wrap items-center gap-3 text-sm"><span>{total} câu hỏi · Trang {page}</span><Button variant="outline" size="sm" disabled={page <= 1 || loading} onClick={() => setPage(page - 1)}>Trước</Button><Button variant="outline" size="sm" disabled={page * 20 >= total || loading} onClick={() => setPage(page + 1)}>Sau</Button></div>
    </CardContent>
    <Dialog open={formOpen} onOpenChange={setFormOpen}><DialogContent className="max-h-[90vh] overflow-y-auto"><DialogHeader><DialogTitle>{editing ? 'Sửa câu hỏi' : 'Thêm câu hỏi'}</DialogTitle></DialogHeader><form className="space-y-4" onSubmit={save}>
      <div className="space-y-2"><Label htmlFor="question-content">Nội dung câu hỏi</Label><Textarea id="question-content" required value={form.content} onChange={e => setForm({ ...form, content: e.target.value })} /></div>
      <div className="grid gap-3 sm:grid-cols-2"><div className="space-y-2"><Label>Loại câu hỏi</Label><Select value={form.type} onValueChange={value => setType(value as QuestionType)}><SelectTrigger aria-label="Loại câu hỏi"><SelectValue /></SelectTrigger><SelectContent>{Object.entries(types).map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}</SelectContent></Select></div><div className="space-y-2"><Label>Độ khó</Label><Select value={form.difficulty} onValueChange={value => setForm({ ...form, difficulty: value as Difficulty })}><SelectTrigger aria-label="Độ khó"><SelectValue /></SelectTrigger><SelectContent>{Object.entries(difficulties).map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}</SelectContent></Select></div></div>
      {form.type !== 'essay' && <fieldset className="space-y-2"><legend className="font-medium text-sm">Đáp án — đánh dấu đáp án đúng</legend>{form.options.map((option, index) => <div className="flex items-center gap-2" key={index}><input type={form.type === 'multiple' ? 'checkbox' : 'radio'} name="correct-answer" aria-label={`Đáp án ${index + 1} đúng`} checked={option.is_correct} onChange={e => setForm({ ...form, options: form.options.map((o, i) => ({ ...o, is_correct: i === index ? e.target.checked : form.type === 'multiple' ? o.is_correct : false })) })} /><Input aria-label={`Nội dung đáp án ${index + 1}`} required value={option.content} onChange={e => setForm({ ...form, options: form.options.map((o, i) => i === index ? { ...o, content: e.target.value } : o) })} />{form.type !== 'true_false' && form.options.length > 2 && <Button type="button" variant="outline" size="sm" onClick={() => setForm({ ...form, options: form.options.filter((_, i) => i !== index) })}>Bỏ</Button>}</div>)}{form.type !== 'true_false' && form.options.length < 6 && <Button type="button" variant="outline" size="sm" onClick={() => setForm({ ...form, options: [...form.options, { content: '', is_correct: false }] })}>Thêm đáp án</Button>}</fieldset>}
      <div className="space-y-2"><Label htmlFor="question-explanation">Giải thích (không bắt buộc)</Label><Textarea id="question-explanation" value={form.explanation || ''} onChange={e => setForm({ ...form, explanation: e.target.value || null })} /></div><DialogFooter><Button type="button" variant="outline" onClick={() => setFormOpen(false)}>Hủy</Button><Button disabled={saving} type="submit">{saving ? 'Đang lưu...' : 'Lưu câu hỏi'}</Button></DialogFooter></form></DialogContent></Dialog>
    <AlertDialog open={!!deleting} onOpenChange={open => { if (!open) setDeleting(null) }}><AlertDialogContent><AlertDialogHeader><AlertDialogTitle>Xóa câu hỏi?</AlertDialogTitle><AlertDialogDescription>Thao tác này xóa câu hỏi khỏi ngân hàng của môn học.</AlertDialogDescription></AlertDialogHeader><AlertDialogFooter><AlertDialogCancel>Hủy</AlertDialogCancel><AlertDialogAction onClick={() => { if (deleting) void questionsApi.remove(deleting.id).then(() => { toast.success('Đã xóa câu hỏi.'); void load() }).catch(error => toast.error(getApiErrorMessage(error, 'Không thể xóa câu hỏi.'))) }}>Xóa</AlertDialogAction></AlertDialogFooter></AlertDialogContent></AlertDialog>
    <Dialog open={importOpen} onOpenChange={setImportOpen}><DialogContent className="max-h-[90vh] overflow-y-auto"><DialogHeader><DialogTitle>Nhập câu hỏi từ Excel</DialogTitle></DialogHeader><p className="text-sm text-muted-foreground">Tối đa 500 dòng, tệp .xlsx tối đa 5 MB. Kiểm tra dòng lỗi trước khi nhập các dòng hợp lệ.</p><Button variant="outline" onClick={() => void downloadTemplate()}>Tải mẫu Excel</Button><Label htmlFor="question-file">Tệp Excel</Label><Input id="question-file" type="file" accept=".xlsx" disabled={importing} onChange={e => void upload(e.target.files?.[0])} />{preview && <div className="space-y-2 text-sm"><p>{preview.valid.length} dòng hợp lệ · {preview.errors.length} dòng lỗi</p>{preview.errors.map(error => <p key={error.row} className="text-destructive">Dòng {error.row}: {error.message}</p>)}</div>}<DialogFooter><Button variant="outline" onClick={() => setImportOpen(false)}>Hủy</Button><Button disabled={importing || !preview?.valid.length} onClick={() => void confirmImport()}>Nhập dòng hợp lệ</Button></DialogFooter></DialogContent></Dialog>
  </Card>
}
