import { useCallback, useEffect, useState } from 'react'
import { Bell } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { learningApi, Notification } from '@/api/learning'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { useAuth } from '@/auth/AuthContext'
import { getApiErrorMessage } from '@/lib/api-error'
import { safeNotificationLink } from '@/lib/notification-link'
import { RemoteState } from './RemoteState'

export function NotificationBell() {
  const [items, setItems] = useState<Notification[]>([]); const [unread, setUnread] = useState(0); const navigate = useNavigate()
  const { user } = useAuth()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const load = useCallback(async () => {
    setError('')
    try { const data = await learningApi.notifications(); setItems(data.items); setUnread(data.unread_count) }
    catch (cause) { setError(getApiErrorMessage(cause, 'Không tải được thông báo.')) }
    finally { setLoading(false) }
  }, [])
  useEffect(() => { load(); const id = window.setInterval(load, 30000); return () => window.clearInterval(id) }, [load])
  const act = async (work: () => Promise<unknown>) => {
    setBusy(true)
    try { await work(); await load() }
    catch (cause) { setError(getApiErrorMessage(cause, 'Không cập nhật được thông báo.')) }
    finally { setBusy(false) }
  }
  const open = (item: Notification) => act(async () => { if (!item.is_read) await learningApi.readNotification(item.id); const link = safeNotificationLink(item.link); if (link) navigate(link) })
  return <DropdownMenu><DropdownMenuTrigger asChild><Button variant="ghost" size="icon" className="relative" aria-label={`Thông báo${unread ? `, ${unread} chưa đọc` : ''}`}><Bell className="h-5 w-5" />{unread > 0 && <Badge className="absolute -right-1 -top-1 min-w-5 justify-center px-1 text-[10px]" variant="destructive">{unread > 99 ? '99+' : unread}</Badge>}</Button></DropdownMenuTrigger><DropdownMenuContent align="end" className="max-h-[80dvh] w-80 max-w-[calc(100vw-2rem)] overflow-y-auto"><DropdownMenuLabel className="flex items-center justify-between">Thông báo{unread > 0 && <Button disabled={busy} variant="link" className="h-auto p-0 text-xs" onClick={() => void act(learningApi.readAll)}>Đọc tất cả</Button>}</DropdownMenuLabel><DropdownMenuSeparator />
    {loading || error ? <div className="p-2"><RemoteState loading={loading} error={error} onRetry={load} /></div> : items.length ? items.slice(0, 8).map(item => <DropdownMenuItem disabled={busy} key={item.id} className="block cursor-pointer whitespace-normal py-2" onClick={() => void open(item)}><div className={item.is_read ? 'font-normal' : 'font-semibold'}>{item.title}</div><p className="mt-0.5 break-words text-xs text-muted-foreground">{item.body}</p></DropdownMenuItem>) : <p className="px-2 py-5 text-center text-sm text-muted-foreground">Chưa có thông báo. Xem lớp học để theo dõi công việc.</p>}
    <DropdownMenuSeparator /><DropdownMenuItem onClick={() => navigate(`/${user?.role}/notifications`)}>Xem tất cả thông báo</DropdownMenuItem>
  </DropdownMenuContent></DropdownMenu>
}
