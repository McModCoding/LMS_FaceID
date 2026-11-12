import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { AlertTriangle, Camera, Pencil, Square } from 'lucide-react'
import { toast } from 'sonner'
import { FaceResult, faceApi, RecognitionFeed } from '@/api/face'
import { attendanceApi } from '@/api/attendance'
import { AttendanceRecord, AttendanceStatus, SessionAttendanceResponse } from '@/types/attendance'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { AttendanceStatusBadge } from '@/components/common/status-badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'

const errorText = (error: unknown, fallback: string) => {
  const data = (error as { response?: { data?: { error?: { message?: string }; detail?: { message?: string } } } }).response?.data
  return data?.error?.message || data?.detail?.message || fallback
}

export default function LiveAttendancePage() {
  const { id } = useParams<{ id: string }>()
  const sessionId = Number(id)
  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const scanBusyRef = useRef(false)
  const [running, setRunning] = useState(false)
  const [ready, setReady] = useState<boolean | null>(null)
  const [engine, setEngine] = useState('')
  const [attendance, setAttendance] = useState<SessionAttendanceResponse | null>(null)
  const [feed, setFeed] = useState<RecognitionFeed>({ needs_confirmation: [], logs: [] })
  const [faces, setFaces] = useState<FaceResult[]>([])
  const [error, setError] = useState('')
  const [editing, setEditing] = useState<AttendanceRecord | null>(null)
  const [manualStatus, setManualStatus] = useState<AttendanceStatus>('present')
  const [note, setNote] = useState('')

  const loadAttendance = useCallback(async () => {
    try { setAttendance(await attendanceApi.getSession(sessionId)); setError('') }
    catch (cause) { setError(errorText(cause, 'Không thể tải danh sách điểm danh.')) }
  }, [sessionId])

  const stop = useCallback(() => {
    const stream = videoRef.current?.srcObject as MediaStream | null
    stream?.getTracks().forEach(track => track.stop())
    if (videoRef.current) videoRef.current.srcObject = null
    setRunning(false); setFaces([])
  }, [])

  useEffect(() => {
    loadAttendance()
    faceApi.status().then(value => { setReady(value.is_ready); setEngine(value.engine) }).catch(cause => setError(errorText(cause, 'Không thể tải trạng thái FaceID.')))
    return stop
  }, [loadAttendance, stop])

  useEffect(() => {
    if (!ready) return
    const loadFeed = () => faceApi.feed(sessionId).then(setFeed).catch(() => undefined)
    loadFeed()
    const timer = window.setInterval(loadFeed, 2000)
    return () => window.clearInterval(timer)
  }, [ready, sessionId])

  useEffect(() => {
    if (!running || !ready) return
    const scan = async () => {
      if (scanBusyRef.current || !videoRef.current || !canvasRef.current || videoRef.current.readyState < 2) return
      scanBusyRef.current = true
      try {
        const video = videoRef.current
        const canvas = canvasRef.current
        canvas.width = video.videoWidth
        canvas.height = video.videoHeight
        canvas.getContext('2d')?.drawImage(video, 0, 0, canvas.width, canvas.height)
        const blob = await new Promise<Blob | null>(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.85))
        if (!blob) return
        const result = await faceApi.recognize(sessionId, blob)
        setFaces(result.faces)
        if (result.attendance_changes.length) await loadAttendance()
      } catch (cause) {
        setError(errorText(cause, 'Quét khuôn mặt thất bại.'))
        stop()
      } finally { scanBusyRef.current = false }
    }
    const timer = window.setInterval(scan, 1000)
    return () => window.clearInterval(timer)
  }, [loadAttendance, ready, running, sessionId, stop])

  const start = async () => {
    if (!ready) return
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true })
      if (videoRef.current) videoRef.current.srcObject = stream
      setRunning(true); setError('')
    } catch { setError('Không thể truy cập camera. Hãy kiểm tra quyền camera của trình duyệt.') }
  }

  const checkIn = async (record: AttendanceRecord) => {
    try { await attendanceApi.checkIn(sessionId, record.student_id); await loadAttendance() }
    catch (cause) { toast.error(errorText(cause, 'Không thể xác nhận có mặt.')) }
  }

  const saveManual = async () => {
    if (!editing) return
    try {
      await attendanceApi.update(sessionId, editing.student_id, { status: manualStatus, note: note.trim() || undefined, expected_status: editing.status })
      setEditing(null); setNote(''); await loadAttendance(); toast.success('Đã cập nhật điểm danh.')
    } catch (cause) { toast.error(errorText(cause, 'Không thể cập nhật điểm danh.')) }
  }

  if (!attendance && !error) return <div className="space-y-4"><Skeleton className="h-9 w-64" /><Skeleton className="h-[28rem] w-full" /></div>

  return <div className="space-y-5">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><h1 className="text-2xl font-semibold">Điểm danh trực tiếp</h1><p className="text-sm text-muted-foreground">Buổi #{sessionId}{engine ? ` · Engine ${engine}` : ''}</p></div><Button asChild variant="outline"><Link to="/lecturer/classes">Quay lại lớp học</Link></Button></div>
    {ready === false && <Alert><AlertTriangle className="h-4 w-4" /><AlertTitle>FaceID chưa kích hoạt</AlertTitle><AlertDescription>Hệ thống đang dùng MockFaceEngine và không sinh kết quả nhận diện giả. Hãy dùng thao tác điểm danh thủ công bên phải.</AlertDescription></Alert>}
    {error && <Alert variant="destructive"><AlertTriangle className="h-4 w-4" /><AlertTitle>Có lỗi xảy ra</AlertTitle><AlertDescription>{error}<Button className="ml-3" size="sm" variant="outline" onClick={loadAttendance}>Thử lại</Button></AlertDescription></Alert>}
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1.5fr)_minmax(20rem,1fr)]">
      <Card><CardHeader><CardTitle className="text-base">Camera nhận diện</CardTitle><CardDescription>{ready ? 'Khi bắt đầu, trình duyệt gửi một khung hình mỗi giây; server không lưu ảnh khung hình.' : 'Camera quét chỉ khả dụng khi engine thật sẵn sàng.'}</CardDescription></CardHeader><CardContent className="space-y-3"><div className="relative aspect-video overflow-hidden rounded-md bg-muted"><video ref={videoRef} autoPlay muted playsInline className="h-full w-full object-cover" />{faces.map((face, index) => <div key={`${face.student_id ?? 'unknown'}-${index}`} className="pointer-events-none absolute border-2 border-primary" style={{ left: `${face.box.x * 100}%`, top: `${face.box.y * 100}%`, width: `${face.box.w * 100}%`, height: `${face.box.h * 100}%` }}><span className="absolute left-0 top-0 bg-primary px-1 text-xs text-primary-foreground">{face.status}</span></div>)}</div><canvas ref={canvasRef} className="hidden" />{running ? <Button variant="outline" onClick={stop}><Square className="mr-2 h-4 w-4" />Dừng quét</Button> : <Button disabled={!ready} onClick={start}><Camera className="mr-2 h-4 w-4" />Bắt đầu quét</Button>}{ready && feed.needs_confirmation.length > 0 && <div className="rounded-md border p-3 text-sm"><p className="font-medium">Cần giảng viên xác nhận ({feed.needs_confirmation.length})</p><p className="mt-1 text-muted-foreground">Các lượt không rõ, mơ hồ hoặc chất lượng thấp không tự thay đổi chuyên cần.</p></div>}</CardContent></Card>
      <Card><CardHeader><CardTitle className="text-base">Tình trạng buổi học</CardTitle><CardDescription>Có thể xác nhận nhanh hoặc chỉnh trạng thái kèm lý do.</CardDescription></CardHeader><CardContent className="space-y-3">{attendance && <><div className="grid grid-cols-2 gap-2 text-sm"><span>Có mặt: {attendance.summary.present}</span><span>Đi muộn: {attendance.summary.late}</span><span>Vắng: {attendance.summary.absent}</span><span>Có phép: {attendance.summary.excused}</span></div><div className="max-h-[28rem] space-y-2 overflow-auto">{attendance.items.map(record => <div className="flex items-center justify-between gap-2 rounded border p-2 text-sm" key={record.id}><div className="min-w-0"><p className="truncate font-medium">{record.full_name}</p><p className="text-muted-foreground">{record.student_code}</p></div><div className="flex shrink-0 items-center gap-1"><AttendanceStatusBadge status={record.display_status} />{record.display_status === 'pending' && <Button size="sm" onClick={() => checkIn(record)}>Có mặt</Button>}<Button size="icon" variant="ghost" aria-label={`Sửa điểm danh ${record.full_name}`} onClick={() => { setEditing(record); setManualStatus(record.status); setNote('') }}><Pencil className="h-4 w-4" /></Button></div></div>)}</div></>}</CardContent></Card>
    </div>
    <Dialog open={Boolean(editing)} onOpenChange={value => !value && setEditing(null)}><DialogContent><DialogHeader><DialogTitle>Sửa điểm danh {editing?.full_name}</DialogTitle><DialogDescription>Hệ thống yêu cầu lý do khi sửa bản ghi đã được người dùng/FaceID đặt hoặc khi buổi đã đóng.</DialogDescription></DialogHeader><div className="space-y-3 py-3"><div className="space-y-1.5"><Label>Trạng thái</Label><Select value={manualStatus} onValueChange={value => setManualStatus(value as AttendanceStatus)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="present">Có mặt</SelectItem><SelectItem value="late">Đi muộn</SelectItem><SelectItem value="absent">Vắng</SelectItem><SelectItem value="excused">Có phép</SelectItem></SelectContent></Select></div><div className="space-y-1.5"><Label htmlFor="manual-note">Lý do</Label><Textarea id="manual-note" value={note} onChange={event => setNote(event.target.value)} maxLength={500} /></div></div><DialogFooter><Button variant="outline" onClick={() => setEditing(null)}>Hủy</Button><Button onClick={saveManual}>Lưu thay đổi</Button></DialogFooter></DialogContent></Dialog>
  </div>
}
