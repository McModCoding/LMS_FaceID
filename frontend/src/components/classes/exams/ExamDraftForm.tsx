import { useCallback, useEffect, useState } from 'react'
import { toast } from 'sonner'
import { examDraftApi, type ExamDraft, type ExamDraftInput, type ExamEvent, type ScorePolicy, type ShowResult } from '@/api/exam-drafts'
import { questionsApi, type Question } from '@/api/questions'
import { getApiErrorMessage } from '@/lib/api-error'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'

type Picked = { question_id: number; content: string; points: string }
const eventLabels: Record<ExamEvent, string> = { tab_hidden: 'Chuyển khỏi thẻ', window_blur: 'Rời cửa sổ', fullscreen_exit: 'Thoát toàn màn hình', copy: 'Sao chép', paste: 'Dán' }

function localInput(value: string): string {
  const parts = new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Ho_Chi_Minh', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(new Date(value))
  return parts.replace(' ', 'T')
}

function errorMessage(error: unknown): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (Array.isArray(detail)) {
    const messages = detail.map(item => typeof item?.msg === 'string' ? item.msg.replace(/^Value error, /, '') : '').filter(Boolean)
    if (messages.length) return messages.join('; ')
  }
  return getApiErrorMessage(error, 'Không thể lưu đề nháp.')
}

export function ExamDraftForm({ classId, subjectId, initial, onCancel, onSaved }: {
  classId: number; subjectId: number; initial: ExamDraft | null; onCancel: () => void; onSaved: () => void
}) {
  const [title, setTitle] = useState(initial?.title ?? '')
  const [description, setDescription] = useState(initial?.description ?? '')
  const [duration, setDuration] = useState(initial ? String(initial.duration_min) : '')
  const [openAt, setOpenAt] = useState(initial ? localInput(initial.open_at) : '')
  const [closeAt, setCloseAt] = useState(initial ? localInput(initial.close_at) : '')
  const [maxAttempts, setMaxAttempts] = useState(initial ? String(initial.max_attempts) : '')
  const [scorePolicy, setScorePolicy] = useState<string>(initial?.score_policy ?? '')
  const [showResult, setShowResult] = useState<string>(initial?.show_result ?? 'after_close')
  const [shuffleQuestions, setShuffleQuestions] = useState(initial?.shuffle_questions ?? false)
  const [shuffleOptions, setShuffleOptions] = useState(initial?.shuffle_options ?? false)
  const [fullscreen, setFullscreen] = useState(initial?.require_fullscreen ?? false)
  const [recordEvents, setRecordEvents] = useState(initial?.record_events ?? false)
  const [eventTypes, setEventTypes] = useState<ExamEvent[]>(initial?.violation_types ?? [])
  const [autoSubmit, setAutoSubmit] = useState(initial?.auto_submit_on_violation ?? false)
  const [maxViolations, setMaxViolations] = useState(String(initial?.max_violations ?? 0))
  const [picked, setPicked] = useState<Picked[]>(initial?.questions.map(q => ({ question_id: q.question_id, content: q.content, points: q.points })) ?? [])
  const [bank, setBank] = useState<Question[]>([])
  const [bankPage, setBankPage] = useState(1)
  const [bankTotal, setBankTotal] = useState(0)
  const [search, setSearch] = useState('')
  const [bankLoading, setBankLoading] = useState(true)
  const [bankError, setBankError] = useState('')
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')

  const loadBank = useCallback(async () => {
    setBankLoading(true); setBankError('')
    try { const data = await questionsApi.list(subjectId, { page: bankPage, page_size: 20, search }); setBank(data.items); setBankTotal(data.total) }
    catch (error) { setBankError(getApiErrorMessage(error, 'Không thể tải câu hỏi.')) }
    finally { setBankLoading(false) }
  }, [subjectId, bankPage, search])
  useEffect(() => { void loadBank() }, [loadBank])

  function move(index: number, direction: number) {
    const target = index + direction
    if (target < 0 || target >= picked.length) return
    const next = [...picked]; [next[index], next[target]] = [next[target], next[index]]; setPicked(next)
  }
  async function submit(event: React.FormEvent) {
    event.preventDefault(); setFormError('')
    if (!scorePolicy || !showResult) { setFormError('Hãy chọn chính sách tính điểm và thời điểm xem kết quả.'); return }
    if (picked.some(item => !item.points || !Number.isFinite(Number(item.points)) || Number(item.points) <= 0)) { setFormError('Điểm của từng câu phải lớn hơn 0.'); return }
    const data: ExamDraftInput = { title, description: description || null, duration_min: Number(duration),
      open_at: `${openAt}:00+07:00`, close_at: `${closeAt}:00+07:00`, max_attempts: Number(maxAttempts),
      score_policy: scorePolicy as ScorePolicy, show_result: showResult as ShowResult, shuffle_questions: shuffleQuestions,
      shuffle_options: shuffleOptions, require_fullscreen: fullscreen, record_events: recordEvents,
      violation_types: recordEvents ? eventTypes : [], max_violations: recordEvents ? Number(maxViolations) : 0,
      auto_submit_on_violation: recordEvents && autoSubmit,
      questions: picked.map(q => ({ question_id: q.question_id, points: q.points })) }
    setSaving(true)
    try { if (initial) await examDraftApi.update(initial.id, data); else await examDraftApi.create(classId, data); toast.success('Đã lưu bài kiểm tra.'); onSaved() }
    catch (error) { setFormError(errorMessage(error)) }
    finally { setSaving(false) }
  }
  return <form onSubmit={submit} className="space-y-5">
    <p className="text-sm text-muted-foreground">Giờ nhập theo Việt Nam (Asia/Ho_Chi_Minh). Lưu đề rồi kiểm tra và công bố trong danh sách bài kiểm tra.</p>
    <div className="space-y-2"><Label htmlFor="exam-title">Tên bài kiểm tra</Label><Input id="exam-title" required maxLength={200} value={title} onChange={e => setTitle(e.target.value)} /></div>
    <div className="space-y-2"><Label htmlFor="exam-description">Hướng dẫn (không bắt buộc)</Label><Textarea id="exam-description" maxLength={10000} value={description} onChange={e => setDescription(e.target.value)} /></div>
    <div className="grid gap-3 sm:grid-cols-2"><div className="space-y-2"><Label htmlFor="exam-open">Mở lúc</Label><Input id="exam-open" type="datetime-local" required value={openAt} onChange={e => setOpenAt(e.target.value)} /></div><div className="space-y-2"><Label htmlFor="exam-close">Đóng lúc</Label><Input id="exam-close" type="datetime-local" required value={closeAt} onChange={e => setCloseAt(e.target.value)} /></div><div className="space-y-2"><Label htmlFor="exam-duration">Thời lượng (phút)</Label><Input id="exam-duration" type="number" min={1} step={1} required value={duration} onChange={e => setDuration(e.target.value)} /></div><div className="space-y-2"><Label htmlFor="exam-attempts">Số lần làm tối đa</Label><Input id="exam-attempts" type="number" min={1} step={1} required value={maxAttempts} onChange={e => setMaxAttempts(e.target.value)} /></div></div>
    <div className="grid gap-3 sm:grid-cols-2"><div className="space-y-2"><Label>Chính sách tính điểm</Label><Select value={scorePolicy} onValueChange={setScorePolicy}><SelectTrigger aria-label="Chính sách tính điểm"><SelectValue placeholder="Chọn chính sách" /></SelectTrigger><SelectContent><SelectItem value="highest">Điểm cao nhất</SelectItem><SelectItem value="last">Lần cuối</SelectItem></SelectContent></Select></div><div className="space-y-2"><Label>Thời điểm xem kết quả</Label><Select value={showResult} onValueChange={setShowResult}><SelectTrigger aria-label="Thời điểm xem kết quả"><SelectValue placeholder="Chọn thời điểm" /></SelectTrigger><SelectContent><SelectItem value="never">Không hiển thị</SelectItem><SelectItem value="after_submit">Sau khi nộp</SelectItem><SelectItem value="after_close">Sau khi đề đóng</SelectItem></SelectContent></Select></div></div>
    <fieldset className="space-y-3"><legend className="font-medium">Chế độ làm bài</legend><label className="flex items-center gap-2 text-sm"><Checkbox checked={shuffleQuestions} onCheckedChange={v => setShuffleQuestions(v === true)} /> Xáo thứ tự câu hỏi</label><label className="flex items-center gap-2 text-sm"><Checkbox checked={shuffleOptions} onCheckedChange={v => setShuffleOptions(v === true)} /> Xáo lựa chọn</label><label className="flex items-center gap-2 text-sm"><Checkbox checked={fullscreen} onCheckedChange={v => { const value = v === true; setFullscreen(value); if (!value) setEventTypes(types => types.filter(t => t !== 'fullscreen_exit')) }} /> Yêu cầu toàn màn hình</label><label className="flex items-center gap-2 text-sm"><Checkbox checked={recordEvents} onCheckedChange={v => { const value = v === true; setRecordEvents(value); if (!value) { setEventTypes([]); setAutoSubmit(false); setMaxViolations('0') } }} /> Ghi nhận sự kiện hành vi</label>
      {recordEvents && <div className="space-y-2 pl-4"><p className="text-sm text-muted-foreground">Sự kiện là chỉ báo cần xem xét, không phải kết luận gian lận.</p>{(Object.keys(eventLabels) as ExamEvent[]).map(type => <label key={type} className="flex items-center gap-2 text-sm"><Checkbox disabled={type === 'fullscreen_exit' && !fullscreen} checked={eventTypes.includes(type)} onCheckedChange={v => setEventTypes(types => v === true ? [...types, type] : types.filter(t => t !== type))} /> {eventLabels[type]}</label>)}<label className="flex items-center gap-2 text-sm"><Checkbox checked={autoSubmit} onCheckedChange={v => setAutoSubmit(v === true)} /> Tự nộp khi đạt ngưỡng</label><div className="space-y-2"><Label htmlFor="exam-violations">Ngưỡng sự kiện (0 = không giới hạn)</Label><Input id="exam-violations" type="number" min={0} step={1} value={maxViolations} onChange={e => setMaxViolations(e.target.value)} /></div></div>}
    </fieldset>
    <fieldset className="space-y-3"><legend className="font-medium">Câu hỏi đã chọn ({picked.length})</legend><p className="text-sm text-muted-foreground">Tối đa 500 câu mỗi đề. Đề nháp tham chiếu ngân hàng. Khi công bố, nội dung và đáp án được đóng băng. Điểm tối đa 4 chữ số thập phân.</p>{picked.length === 0 && <p className="text-sm text-muted-foreground">Chưa chọn câu hỏi. Có thể lưu đề nháp và bổ sung sau.</p>}{picked.map((item, index) => <div key={item.question_id} className="rounded-md border p-3 space-y-2"><p className="break-words">{index + 1}. {item.content}</p><div className="flex flex-wrap items-end gap-2"><div><Label htmlFor={`points-${item.question_id}`}>Điểm</Label><Input id={`points-${item.question_id}`} className="w-28" type="number" required min="0.0001" step="0.0001" value={item.points} onChange={e => setPicked(rows => rows.map(q => q.question_id === item.question_id ? { ...q, points: e.target.value } : q))} /></div><Button type="button" size="sm" variant="outline" disabled={index === 0} onClick={() => move(index, -1)}>Lên</Button><Button type="button" size="sm" variant="outline" disabled={index === picked.length - 1} onClick={() => move(index, 1)}>Xuống</Button><Button type="button" size="sm" variant="outline" onClick={() => setPicked(rows => rows.filter(q => q.question_id !== item.question_id))}>Bỏ câu</Button></div></div>)}</fieldset>
    <fieldset className="space-y-3"><legend className="font-medium">Chọn từ ngân hàng của môn</legend><Input aria-label="Tìm câu hỏi" placeholder="Tìm câu hỏi" value={search} onChange={e => { setSearch(e.target.value); setBankPage(1) }} />{bankLoading ? <Skeleton className="h-20 w-full" /> : bankError ? <div role="alert"><p>{bankError}</p><Button type="button" variant="outline" onClick={() => void loadBank()}>Thử lại</Button></div> : bank.length === 0 ? <p className="text-sm text-muted-foreground">Không có câu hỏi phù hợp. Hãy thêm câu trong ngân hàng hoặc đổi từ khóa.</p> : bank.map(q => <div className="flex flex-wrap items-center justify-between gap-2 border-b py-2" key={q.id}><span className="break-words min-w-0">{q.content}</span><Button type="button" size="sm" variant="outline" disabled={picked.some(item => item.question_id === q.id)} onClick={() => setPicked(rows => [...rows, { question_id: q.id, content: q.content, points: '' }])}>{picked.some(item => item.question_id === q.id) ? 'Đã chọn' : 'Chọn'}</Button></div>)}<div className="flex flex-wrap items-center gap-2 text-sm"><span>{bankTotal} câu · Trang {bankPage}</span><Button type="button" size="sm" variant="outline" disabled={bankPage <= 1 || bankLoading} onClick={() => setBankPage(p => p - 1)}>Trước</Button><Button type="button" size="sm" variant="outline" disabled={bankPage * 20 >= bankTotal || bankLoading} onClick={() => setBankPage(p => p + 1)}>Sau</Button></div></fieldset>
    {formError && <p role="alert" className="text-sm text-destructive">{formError}</p>}<div className="flex flex-wrap justify-end gap-2"><Button type="button" variant="outline" onClick={onCancel}>Hủy</Button><Button type="submit" disabled={saving}>{saving ? 'Đang lưu...' : initial?.status === 'published' ? 'Lưu thay đổi' : 'Lưu đề nháp'}</Button></div>
  </form>
}
