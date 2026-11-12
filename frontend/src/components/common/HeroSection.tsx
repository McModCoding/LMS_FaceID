import { Link } from 'react-router-dom'
import { cn } from '@/lib/utils'

interface HeroSectionProps {
  tag: string
  title: string
  description?: string
  variant?: 'blue' | 'teal' | 'warm'
  action?: { label: string; href: string }
  className?: string
}

const variantClass = {
  blue: 'bg-accent border-accent/60',
  teal: 'bg-[hsl(175_60%_90%)] border-[hsl(175_60%_80%)] dark:bg-[hsl(175_30%_18%)] dark:border-[hsl(175_30%_28%)]',
  warm: 'bg-[hsl(37_80%_93%)] border-[hsl(37_80%_82%)] dark:bg-[hsl(37_30%_18%)] dark:border-[hsl(37_30%_28%)]',
}

export function HeroSection({
  tag,
  title,
  description,
  variant = 'blue',
  action,
  className,
}: HeroSectionProps) {
  return (
    <div
      className={cn(
        'flex flex-wrap items-center justify-between gap-4 rounded-xl border p-5',
        variantClass[variant],
        className,
      )}
    >
      <div className="min-w-0">
        <p className="text-xs font-bold uppercase tracking-wider text-primary">{tag}</p>
        <h2 className="mt-1 text-xl font-semibold">{title}</h2>
        {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
      </div>
      {action && (
        <Link
          to={action.href}
          className="shrink-0 inline-flex h-9 items-center rounded-md bg-primary px-4 text-sm font-semibold text-primary-foreground hover:opacity-90"
        >
          {action.label}
        </Link>
      )}
    </div>
  )
}
