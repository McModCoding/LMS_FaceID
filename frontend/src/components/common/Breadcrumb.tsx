import { Fragment } from 'react'
import { Link } from 'react-router-dom'
import { ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'

export interface BreadcrumbItem {
  label: string
  href?: string
}

export function AppBreadcrumb({ items, className }: { items: BreadcrumbItem[]; className?: string }) {
  if (!items.length) return null
  return (
    <nav aria-label="Breadcrumb" className={cn('flex items-center gap-1 text-sm text-muted-foreground', className)}>
      {items.map((item, i) => (
        <Fragment key={i}>
          {i > 0 && <ChevronRight className="h-3.5 w-3.5 shrink-0 opacity-50" />}
          {item.href
            ? <Link to={item.href} className="max-w-[200px] truncate hover:text-foreground transition-colors">{item.label}</Link>
            : <span className="max-w-[200px] truncate font-medium text-foreground">{item.label}</span>
          }
        </Fragment>
      ))}
    </nav>
  )
}
