import { TabsList, TabsTrigger } from '@/components/ui/tabs'
import { cn } from '@/lib/utils'

type Item = { value: string; label: string; group: string }
const items: Item[] = [
  { value: 'info', label: 'Tổng quan lớp', group: 'Tổng quan' },
  { value: 'announcements', label: 'Thông báo', group: 'Tổng quan' },
  { value: 'schedules', label: 'Lịch & buổi học', group: 'Lịch & chuyên cần' },
  { value: 'attendance', label: 'Điểm danh', group: 'Lịch & chuyên cần' },
  { value: 'leave', label: 'Đơn xin vắng', group: 'Lịch & chuyên cần' },
  { value: 'report', label: 'Báo cáo chuyên cần', group: 'Lịch & chuyên cần' },
  { value: 'materials', label: 'Học liệu', group: 'Học tập' },
  { value: 'assignments', label: 'Bài tập', group: 'Học tập' },
  { value: 'exams', label: 'Bài kiểm tra', group: 'Đánh giá' },
  { value: 'questions', label: 'Ngân hàng câu hỏi', group: 'Đánh giá' },
  { value: 'grades', label: 'Bảng điểm', group: 'Đánh giá' },
  { value: 'students', label: 'Sinh viên', group: 'Thành viên' },
  { value: 'groups', label: 'Nhóm', group: 'Thành viên' },
]

export function ClassNavigation({
  value,
  onChange,
  student = false,
}: {
  value: string
  onChange: (value: string) => void
  student?: boolean
}) {
  const available = items
    .filter((item) => !student || !['students', 'report', 'questions'].includes(item.value))
    .map((item) => (student && item.value === 'attendance' ? { ...item, label: 'Chuyên cần của tôi' } : item))

  const groups = [...new Set(available.map((item) => item.group))]
  const selected = available.find((item) => item.value === value)?.group || groups[0]

  return (
    <nav aria-label="Điều hướng lớp học" className="space-y-2.5">

      <div
        className="flex flex-wrap items-center gap-1.5 rounded-xl border border-border/70 bg-muted/70 p-1.5 shadow-xs"
        aria-label="Nhóm chức năng trong lớp"
      >
        {groups.map((group) => {
          const isSelected = selected === group
          return (
            <button
              key={group}
              type="button"
              className={cn(
                'inline-flex items-center justify-center rounded-lg px-3.5 py-1.5 text-xs sm:text-sm font-medium transition-all duration-150',
                isSelected
                  ? 'bg-background text-foreground font-semibold shadow-xs border border-border/50'
                  : 'text-muted-foreground hover:text-foreground hover:bg-background/40'
              )}
              aria-pressed={isSelected}
              onClick={() => onChange(available.find((item) => item.group === group)!.value)}
            >
              {group}
            </button>
          )
        })}
      </div>

      <TabsList
        aria-label={`Các mục trong nhóm ${selected}`}
        className="hidden h-auto w-full flex-wrap justify-start gap-1.5 rounded-xl border border-border/70 bg-card p-2 shadow-xs sm:flex"
      >
        {available
          .filter((item) => item.group === selected)
          .map((item) => (
            <TabsTrigger
              key={item.value}
              value={item.value}
              className="rounded-lg px-3.5 py-1.5 text-xs sm:text-sm font-medium transition-all border border-transparent data-[state=active]:bg-primary/10 data-[state=active]:text-primary data-[state=active]:font-semibold data-[state=active]:border-primary/20 text-muted-foreground hover:text-foreground hover:bg-muted/50"
            >
              {item.label}
            </TabsTrigger>
          ))}
      </TabsList>

      <div className="block rounded-xl border border-border/70 bg-card p-3 shadow-xs sm:hidden">
        <label className="space-y-1.5 block">
          <span className="text-xs font-medium text-muted-foreground">Mục trong {selected.toLowerCase()}</span>
          <select
            aria-label="Mục trong lớp"
            className="h-10 w-full rounded-lg border border-input bg-background px-3 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            value={value}
            onChange={(event) => onChange(event.target.value)}
          >
            {available
              .filter((item) => item.group === selected)
              .map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
          </select>
        </label>
      </div>
    </nav>
  )
}
