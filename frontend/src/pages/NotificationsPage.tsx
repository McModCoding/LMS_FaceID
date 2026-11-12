import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '@/api/client'
import { learningApi, type Notification } from '@/api/learning'
import { RemoteState, Pagination } from '@/components/common/RemoteState'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { getApiErrorMessage } from '@/lib/api-error'
import { safeNotificationLink } from '@/lib/notification-link'

export default function NotificationsPage() {
  const navigate = useNavigate()
  const [items, setItems] = useState<Notification[]>([])
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [unread, setUnread] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [actionError, setActionError] = useState('')
  const load = useCallback(async () => {
    setLoading(true); setError('')
    try { const { data } = await api.get('/notifications', { params: { page, page_size: 20 } }); setItems(data.items); setTotal(data.total); setUnread(data.unread_count) }
    catch (cause) { setError(getApiErrorMessage(cause, 'Không tải được thông báo.')) }
    finally { setLoading(false) }
  }, [page])
  useEffect(() => { void load() }, [load])
  const act = async (work: () => Promise<unknown>) => {
    setBusy(true); setActionError('')
    try { await work(); await load() }
    catch (cause) { setActionError(getApiErrorMessage(cause, 'Không cập nhật được thông báo.')) }
    finally { setBusy(false) }
  }
  return <main className="min-w-0 space-y-4"><h1 className="text-2xl font-semibold">Thông báo của tôi</h1><div className="flex flex-wrap items-center gap-3"><p className="text-sm">{unread} thông báo chưa đọc</p><Button variant="outline" disabled={!unread || busy || loading} onClick={() => void act(learningApi.readAll)}>Đánh dấu tất cả đã đọc</Button></div>
    {actionError && <p role="alert" className="text-sm text-destructive">{actionError}</p>}
    <RemoteState loading={loading} error={error} onRetry={load} empty={!items.length ? 'Chưa có thông báo. Hãy mở danh sách lớp để xem bài tập, lịch học và các công việc hiện có.' : ''} />
    {!loading && !error && <><div className="space-y-3">{items.map(item => <Card key={item.id}><CardContent className="min-w-0 space-y-2 pt-4"><h2 className="break-words font-medium">{item.title} · {item.is_read ? 'Đã đọc' : 'Chưa đọc'}</h2><p className="whitespace-pre-wrap break-words text-sm">{item.body}</p><p className="text-xs text-muted-foreground">{new Date(item.created_at).toLocaleString('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh' })}</p><div className="flex flex-wrap gap-2">{!item.is_read && <Button variant="outline" size="sm" disabled={busy} onClick={() => void act(() => learningApi.readNotification(item.id))}>Đánh dấu đã đọc</Button>}{safeNotificationLink(item.link) && <Button size="sm" disabled={busy} onClick={() => void act(async () => { if (!item.is_read) await learningApi.readNotification(item.id); navigate(safeNotificationLink(item.link)!) })}>Mở nội dung</Button>}</div></CardContent></Card>)}</div><Pagination page={page} total={total} loading={loading} onChange={setPage} /></>}
  </main>
}
