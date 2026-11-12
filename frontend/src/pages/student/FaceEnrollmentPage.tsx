import { useCallback, useEffect, useState } from 'react'
import { Camera, ShieldCheck, Trash2, Upload } from 'lucide-react'
import { toast } from 'sonner'
import { FaceEnrollmentResult, faceApi, FaceProfile } from '@/api/face'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'

const CONSENT_VERSION = 'v1.0'
const reasonLabels: Record<string, string> = {
  unsupported_type: 'Sai định dạng',
  empty_file: 'Tệp rỗng',
  file_too_large: 'Vượt quá 10 MB',
  invalid_image: 'Nội dung không phải ảnh hợp lệ',
  no_face: 'Không tìm thấy khuôn mặt',
  multiple_faces: 'Ảnh có nhiều khuôn mặt',
  blurry: 'Ảnh bị mờ',
  too_dark: 'Ảnh quá tối',
  too_bright: 'Ảnh quá sáng',
  face_too_small: 'Khuôn mặt quá nhỏ, hãy lại gần camera',
  low_contrast: 'Độ tương phản thấp',
  tilted_head: 'Đầu nghiêng quá nhiều',
  near_edge: 'Khuôn mặt sát mép ảnh',
  feature_failed: 'Không trích xuất được đặc trưng',
}

const errorText = (error: unknown, fallback: string) => {
  const data = (error as { response?: { data?: { error?: { message?: string }; detail?: { message?: string } } } }).response?.data
  return data?.error?.message || data?.detail?.message || fallback
}

export default function FaceEnrollmentPage() {
  const [profile, setProfile] = useState<FaceProfile | null>(null)
  const [agreed, setAgreed] = useState(false)
  const [files, setFiles] = useState<File[]>([])
  const [result, setResult] = useState<FaceEnrollmentResult | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [confirmRevoke, setConfirmRevoke] = useState(false)

  const load = useCallback(async () => {
    setError('')
    try { setProfile(await faceApi.getProfile()) }
    catch (cause) { setError(errorText(cause, 'Không thể tải hồ sơ khuôn mặt.')) }
  }, [])
  useEffect(() => { load() }, [load])

  const consent = async () => {
    setSaving(true)
    try { await faceApi.consent(CONSENT_VERSION); await load(); toast.success('Đã ghi nhận sự đồng ý của bạn.') }
    catch (cause) { toast.error(errorText(cause, 'Không thể ghi nhận sự đồng ý.')) }
    finally { setSaving(false) }
  }

  const enroll = async () => {
    setSaving(true)
    try {
      const response = await faceApi.enroll(files)
      setResult(response); setFiles([]); await load()
      if (response.accepted) toast.success(`Đã lưu ${response.accepted} ảnh ở trạng thái chờ xử lý.`)
      if (response.rejected) toast.warning(`${response.rejected} ảnh không được chấp nhận. Xem lý do bên dưới.`)
    } catch (cause) { await load(); toast.error(errorText(cause, 'Không thể đăng ký ảnh.')) }
    finally { setSaving(false) }
  }

  const revoke = async () => {
    setSaving(true)
    try { await faceApi.revoke(); setResult(null); setConfirmRevoke(false); await load(); toast.success('Đã thu hồi đồng ý và xóa dữ liệu khuôn mặt.') }
    catch (cause) { setResult(null); setConfirmRevoke(false); await load(); toast.error(errorText(cause, 'Không thể xóa hết dữ liệu; hãy tải lại hồ sơ và thử lại.')) }
    finally { setSaving(false) }
  }

  if (!profile && !error) return <div className="space-y-4"><Skeleton className="h-8 w-56" /><Skeleton className="h-64 w-full" /></div>
  if (error && !profile) return <div className="rounded-md border border-destructive/40 p-5"><p className="text-sm text-destructive">{error}</p><Button className="mt-3" variant="outline" onClick={load}>Thử lại</Button></div>

  return <div className="mx-auto max-w-2xl space-y-5"><div><h1 className="text-2xl font-semibold">Đăng ký khuôn mặt</h1><p className="mt-1 text-sm text-muted-foreground">Ảnh chỉ được lưu sau khi bạn đồng ý, dùng để tạo vector đặc trưng khi FaceID đã được kích hoạt. Hệ thống không tạo nhận diện giả; bạn có thể thu hồi và xóa dữ liệu bất cứ lúc nào.</p></div>{error && <div role="alert" className="rounded-md border border-destructive/40 p-3 text-sm"><p className="text-destructive">{error}</p><Button className="mt-2" variant="outline" onClick={load}>Thử lại</Button></div>}{profile?.cleanup_pending && <div role="alert" className="space-y-2 rounded-md border border-warning/40 bg-warning/10 p-3 text-sm"><p>Còn dữ liệu ảnh cần xóa. Hãy thử xóa trước khi đồng ý lại hoặc đăng ký thêm ảnh. Thao tác này cũng thu hồi sự đồng ý hiện tại nếu có.</p><Button variant="outline" disabled={saving} onClick={() => setConfirmRevoke(true)}>Thử xóa dữ liệu còn lại</Button></div>}<Card><CardHeader><CardTitle className="flex items-center gap-2"><ShieldCheck className="h-5 w-5 text-primary" />Sự đồng ý xử lý dữ liệu</CardTitle><CardDescription>Ảnh không hiển thị công khai. Bạn có thể thu hồi; hệ thống chỉ báo thành công khi xóa được toàn bộ tệp đã lưu.</CardDescription></CardHeader><CardContent className="space-y-4">{!profile?.consented ? <><label className="flex items-start gap-3 text-sm"><Checkbox checked={agreed} onCheckedChange={value => setAgreed(value === true)} aria-label="Đồng ý xử lý dữ liệu khuôn mặt" /><span>Tôi đã đọc và đồng ý để nhà trường lưu ảnh khuôn mặt nhằm phục vụ điểm danh theo phiên bản {CONSENT_VERSION}.</span></label><Button disabled={!agreed || saving || profile?.cleanup_pending} onClick={consent}>Xác nhận đồng ý</Button></> : <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border bg-muted/40 p-3 text-sm"><span>Đã đồng ý · {profile.image_count} ảnh · {profile.status === 'active' ? 'Đã kích hoạt' : 'Chờ engine xử lý'}</span><Button variant="outline" disabled={saving} onClick={() => setConfirmRevoke(true)}><Trash2 className="mr-2 h-4 w-4" />Thu hồi & xóa dữ liệu</Button></div>}</CardContent></Card>{profile?.consented && <Card><CardHeader><CardTitle className="flex items-center gap-2"><Camera className="h-5 w-5 text-primary" />Ảnh đăng ký</CardTitle><CardDescription>Chọn 1–5 ảnh JPG/PNG, tối đa 10 MB mỗi ảnh. Tên đuôi, MIME và chữ ký nội dung đều được kiểm tra.</CardDescription></CardHeader><CardContent className="space-y-4"><Input disabled={saving || profile?.cleanup_pending} type="file" accept="image/jpeg,image/png" multiple onChange={event => { setFiles(Array.from(event.target.files || []).slice(0, 5)); setResult(null) }} />{files.length > 0 && <p className="text-sm text-muted-foreground">Đã chọn {files.length} ảnh.</p>}<Button disabled={saving || files.length === 0 || profile?.cleanup_pending} onClick={enroll}><Upload className="mr-2 h-4 w-4" />Lưu ảnh đăng ký</Button>{result && <div className="space-y-2 rounded-md border p-3 text-sm">{result.items.map((item, index) => <div className="flex items-center justify-between gap-3" key={`${item.filename}-${index}`}><span className="truncate">{item.filename || `Ảnh ${index + 1}`}</span><Badge variant={item.accepted ? 'success' : 'destructive'}>{item.accepted ? 'Đã lưu' : reasonLabels[item.reason || ''] || 'Không đạt'}</Badge></div>)}</div>}</CardContent></Card>}<AlertDialog open={confirmRevoke} onOpenChange={setConfirmRevoke}><AlertDialogContent><AlertDialogHeader><AlertDialogTitle>Thu hồi đồng ý và xóa dữ liệu?</AlertDialogTitle><AlertDialogDescription>Ảnh đăng ký và embedding sẽ bị xóa. Nếu dùng FaceID thật sau này, bạn phải đăng ký lại.</AlertDialogDescription></AlertDialogHeader><AlertDialogFooter><AlertDialogCancel>Hủy</AlertDialogCancel><AlertDialogAction className="bg-destructive text-destructive-foreground hover:bg-destructive/90" disabled={saving} onClick={revoke}>Thu hồi & xóa</AlertDialogAction></AlertDialogFooter></AlertDialogContent></AlertDialog></div>
}
