import * as React from 'react'
import { cn } from '@/lib/utils'

type CheckboxProps = Omit<React.InputHTMLAttributes<HTMLInputElement>, 'type' | 'onChange'> & {
  checked?: boolean
  onCheckedChange?: (checked: boolean) => void
}

export const Checkbox = React.forwardRef<HTMLInputElement, CheckboxProps>(
  ({ className, checked, onCheckedChange, ...props }, ref) => (
    <input ref={ref} type="checkbox" checked={checked} onChange={(event) => onCheckedChange?.(event.target.checked)} className={cn('h-4 w-4 rounded border-input accent-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring', className)} {...props} />
  ),
)
Checkbox.displayName = 'Checkbox'
