import { useCallback, useEffect, useState } from 'react'
import { api } from '@/api/client'
import { RemoteState } from '@/components/common/RemoteState'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { getApiErrorMessage } from '@/lib/api-error'

interface Info { environment: string; timezone: string; max_upload_mb: number; access_token_minutes: number; login_attempts: number; login_lockout_minutes: number; exam_grace_seconds: number; attendance_edit_hours: number; face_engine: string; face_ready: boolean; demo_open_anytime: boolean }
export default function SystemInfoPage() {
  const [data, setData] = useState<Info | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const load = useCallback(async () => {
    setLoading(true); setError('')
    try { setData((await api.get<Info>('/admin/system-info')).data) }
    catch (cause) { setError(getApiErrorMessage(cause, 'Không tải được thông số vận hành.')) }
    finally { setLoading(false) }
  }, [])
  useEffect(() => { void load() }, [load])
  return <main className="space-y-4"><h1 className="text-2xl font-semibold">Thông số vận hành</h1><p className="text-sm text-muted-foreground">Thông tin chỉ xem dành cho Admin. Thay đổi thông số cần quản trị triển khai; không hiển thị mật khẩu hoặc khóa xác thực.</p><RemoteState loading={loading} error={error} onRetry={load} />{!loading && !error && data && <>
    <Card><CardHeader><CardTitle>Hệ thống và tài khoản</CardTitle></CardHeader><CardContent><dl className="grid gap-4 sm:grid-cols-2">{[
      ['Môi trường', { development: 'Phát triển', test: 'Kiểm thử', production: 'Vận hành' }[data.environment] || data.environment],
      ['Múi giờ nghiệp vụ', data.timezone], ['Tệp tải lên tối đa', `${data.max_upload_mb} MB`],
      ['Thời hạn phiên truy cập', `${data.access_token_minutes} phút`], ['Giới hạn đăng nhập sai', `${data.login_attempts} lần / ${data.login_lockout_minutes} phút`],
      ['Khoảng nhận đáp án cuối', `${data.exam_grace_seconds} giây`], ['Cửa sổ giảng viên sửa điểm danh', `${data.attendance_edit_hours} giờ sau đóng buổi`],
      ['Mở buổi ngoài giờ để demo', data.demo_open_anytime ? 'Đang bật' : 'Đang tắt'],
    ].map(([label, value]) => <div key={label}><dt className="text-sm text-muted-foreground">{label}</dt><dd className="break-words font-medium">{value}</dd></div>)}</dl></CardContent></Card>
    <Card><CardHeader><CardTitle>Trạng thái FaceID</CardTitle></CardHeader><CardContent className="space-y-2"><p>{data.face_engine} · {data.face_ready ? 'Đã sẵn sàng' : 'Chưa sẵn sàng'}</p><p className="text-sm text-muted-foreground">Khi engine chưa sẵn sàng, giảng viên điểm danh thủ công. Không có kết quả nhận diện giả.</p></CardContent></Card>
  </>}</main>
}
