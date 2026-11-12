import { useEffect, useState } from 'react'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { getApiErrorMessage } from '@/lib/api-error'

export type SearchOption = { value: string; label: string }
type SearchResult = { items: SearchOption[]; total: number }

/** A bounded server-side search: the current selection remains visible when the query changes. */
export function RemoteSearchSelect({ value, onChange, label, emptyValue, emptyLabel, search, selectedLabel }: {
  value: string
  onChange: (value: string) => void
  label: string
  emptyValue: string
  emptyLabel: string
  search: (query: string) => Promise<SearchResult>
  selectedLabel?: string
}) {
  const [query, setQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [result, setResult] = useState<SearchResult>({ items: [], total: 0 })
  const [selected, setSelected] = useState<SearchOption | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedQuery(query.trim()), 300)
    return () => window.clearTimeout(timer)
  }, [query])
  useEffect(() => {
    let active = true
    setLoading(true); setError('')
    void search(debouncedQuery).then((data) => { if (active) setResult(data) }).catch((err: unknown) => {
      if (active) { setResult({ items: [], total: 0 }); setError(getApiErrorMessage(err, `Không thể tải ${label.toLowerCase()}.`)) }
    }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [debouncedQuery, search, retry, label])

  const current = result.items.find((item) => item.value === value) || (selected?.value === value ? selected : null) || (value !== emptyValue && selectedLabel ? { value, label: selectedLabel } : null)
  const options = current && !result.items.some((item) => item.value === current.value) ? [current, ...result.items] : result.items
  return <div className="space-y-1">
    <Input aria-label={`Tìm ${label.toLowerCase()}`} placeholder={`Tìm ${label.toLowerCase()} theo mã hoặc tên`} value={query} onChange={(event) => setQuery(event.target.value)} />
    <Select value={value} onValueChange={(next) => { setSelected(options.find((item) => item.value === next) || null); onChange(next) }}>
      <SelectTrigger aria-label={label}><SelectValue placeholder={emptyLabel} /></SelectTrigger>
      <SelectContent><SelectItem value={emptyValue}>{emptyLabel}</SelectItem>{options.map((item) => <SelectItem key={item.value} value={item.value}>{item.label}</SelectItem>)}</SelectContent>
    </Select>
    {loading ? <p className="text-xs text-muted-foreground">Đang tải lựa chọn…</p> : error ? <div role="alert" className="text-xs"><p>{error}</p><Button type="button" variant="outline" size="sm" onClick={() => setRetry((currentRetry) => currentRetry + 1)}>Thử lại</Button></div> : result.total > result.items.length ? <p className="text-xs text-muted-foreground">Hiển thị {result.items.length} / {result.total} kết quả. Nhập thêm để tìm chính xác hơn.</p> : null}
  </div>
}
