import { useCallback, useEffect, useState } from 'react'
import { AlertTriangle, RefreshCw, ScanFace } from 'lucide-react'
import { toast } from 'sonner'
import { faceApi } from '@/api/face'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'

type EngineStatus = { engine: string; version: string; is_ready: boolean }

const errorText = (error: unknown, fallback: string) => {
  const data = (error as { response?: { data?: { error?: { message?: string }; detail?: { message?: string } } } }).response?.data
  return data?.error?.message || data?.detail?.message || fallback
}

export default function FaceSettingsPage() {
  const [status, setStatus] = useState<EngineStatus | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)

  const load = useCallback(async () => {
    setLoading(true); setError('')
    try { setStatus(await faceApi.status()) }
    catch (cause) { setError(errorText(cause, 'Không thể tải trạng thái FaceID.')) }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  const reindex = async () => {
    setRunning(true)
    try {
      const result = await faceApi.reindex()
      toast.success(`Đã xử lý ${result.processed} ảnh, kích hoạt ${result.activated} mẫu.`)
    } catch (cause) { toast.error(errorText(cause, 'Không thể reindex dữ liệu khuôn mặt.')) }
    finally { setRunning(false) }
  }

  return <div className="space-y-5"><div><h1 className="text-2xl font-semibold">Cấu hình FaceID</h1><p className="mt-1 text-sm text-muted-foreground">Theo dõi hợp đồng engine và xử lý lại ảnh đăng ký khi engine thật sẵn sàng.</p></div>{loading ? <Skeleton className="h-48 w-full" /> : error ? <Alert variant="destructive"><AlertTriangle className="h-4 w-4" /><AlertTitle>Không thể tải trạng thái</AlertTitle><AlertDescription>{error}<Button className="ml-3" size="sm" variant="outline" onClick={load}>Thử lại</Button></AlertDescription></Alert> : status && <><Alert><AlertTriangle className="h-4 w-4" /><AlertTitle>{status.is_ready ? 'Engine đã sẵn sàng' : 'FaceID chưa kích hoạt'}</AlertTitle><AlertDescription>{status.is_ready ? 'Có thể reindex các ảnh đang chờ xử lý.' : 'Hệ thống đang dùng MockFaceEngine. Không có kết quả nhận diện giả; giảng viên vẫn điểm danh thủ công.'}</AlertDescription></Alert><Card><CardHeader><CardTitle className="flex items-center gap-2"><ScanFace className="h-5 w-5 text-primary" />Trạng thái engine</CardTitle><CardDescription>FaceID thật chỉ được triển khai tại M9.</CardDescription></CardHeader><CardContent className="space-y-4"><dl className="grid gap-3 text-sm sm:grid-cols-3"><div><dt className="text-muted-foreground">Engine</dt><dd className="font-medium">{status.engine}</dd></div><div><dt className="text-muted-foreground">Phiên bản</dt><dd className="font-medium">{status.version}</dd></div><div><dt className="text-muted-foreground">Sẵn sàng</dt><dd><Badge variant={status.is_ready ? 'success' : 'secondary'}>{status.is_ready ? 'Có' : 'Chưa'}</Badge></dd></div></dl><Button disabled={!status.is_ready || running} onClick={reindex}><RefreshCw className="mr-2 h-4 w-4" />{running ? 'Đang xử lý…' : 'Reindex ảnh đang chờ'}</Button>{!status.is_ready && <p className="text-xs text-muted-foreground">Nút bị khóa đúng thiết kế. API sẽ trả 409 nếu gọi reindex khi engine mock.</p>}</CardContent></Card></>}</div>
}
