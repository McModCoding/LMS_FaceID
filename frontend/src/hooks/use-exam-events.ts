import { useEffect, useMemo, useRef, useState } from 'react'
import { examManagementApi } from '@/api/exam-management'
import { getApiErrorMessage } from '@/lib/api-error'

// Retry the same UUID within this page session; never send clipboard content.
export function useExamEvents(attemptId: number, enabled: boolean, fullscreen: boolean, onReceipt: (value: { violation_count: number; status: string; is_auto_submitted: boolean }) => void) {
  const callback = useRef(onReceipt)
  callback.current = onReceipt
  const session = useMemo(() => ({ queue: [] as { id: string; type: string }[], sending: false }), [attemptId])
  const [error, setError] = useState('')
  useEffect(() => {
    if (!enabled) { session.queue = []; return }
    let disposed = false
    const flush = async () => {
      if (session.sending || !navigator.onLine) return
      session.sending = true
      try {
        while (!disposed && session.queue.length) {
          const item = session.queue[0]
          const receipt = await examManagementApi.event(attemptId, item.id, item.type)
          if (disposed) return
          session.queue.shift(); setError(''); callback.current(receipt)
          if (receipt.status !== 'in_progress') { session.queue = []; break }
        }
      } catch (cause) { if (!disposed) setError(getApiErrorMessage(cause, 'Nhật ký chưa đồng bộ. Hệ thống sẽ thử lại khi có kết nối.')) }
      finally { session.sending = false }
    }
    const record = (type: string) => {
      if (session.queue.length >= 200) { setError('Nhật ký chưa đồng bộ do mất kết nối kéo dài. Hãy giữ trang mở và kiểm tra kết nối.'); return }
      session.queue.push({ id: crypto.randomUUID(), type }); void flush()
    }
    const hidden = () => { if (document.hidden) record('tab_hidden') }
    const blur = () => record('window_blur')
    const exit = () => { if (fullscreen && !document.fullscreenElement) record('fullscreen_exit') }
    const copy = () => record('copy')
    const paste = () => record('paste')
    const online = () => record('reconnect')
    document.addEventListener('visibilitychange', hidden)
    window.addEventListener('blur', blur)
    document.addEventListener('fullscreenchange', exit)
    document.addEventListener('copy', copy)
    document.addEventListener('paste', paste)
    window.addEventListener('online', online)
    const timer = window.setInterval(() => { void flush() }, 5000)
    return () => {
      disposed = true; window.clearInterval(timer)
      document.removeEventListener('visibilitychange', hidden); window.removeEventListener('blur', blur)
      document.removeEventListener('fullscreenchange', exit); document.removeEventListener('copy', copy)
      document.removeEventListener('paste', paste); window.removeEventListener('online', online)
    }
  }, [attemptId, enabled, fullscreen, session])
  return error
}
