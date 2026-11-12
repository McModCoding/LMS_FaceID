import { Component, type ReactNode } from 'react'
import { Button } from '@/components/ui/button'

export class PageLoadBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  render() {
    if (this.state.failed) return <main role="alert" className="mx-auto max-w-xl space-y-4 p-6"><h1 className="text-xl font-semibold">Không mở được màn hình</h1><p>Kiểm tra kết nối và tải lại trang. Những thay đổi đã lưu trên máy chủ vẫn được giữ.</p><Button onClick={() => window.location.reload()}>Tải lại trang</Button></main>
    return this.props.children
  }
}
