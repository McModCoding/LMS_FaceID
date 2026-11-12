import { Menu } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { cn } from '@/lib/utils'

type Item = { key: string; label: string; icon: React.ReactNode }

export function MobileNavigation({ items, pathname, title }: { items: Item[]; pathname: string; title: string }) {
  const [open, setOpen] = useState(false)
  return <Dialog open={open} onOpenChange={setOpen}><Button variant="ghost" size="icon" className="md:hidden" aria-label="Mở menu điều hướng" onClick={() => setOpen(true)}><Menu className="h-5 w-5" /></Button><DialogContent className="left-0 top-0 h-dvh max-w-[18rem] translate-x-0 translate-y-0 rounded-none p-4 data-[state=closed]:slide-out-to-left data-[state=open]:slide-in-from-left"><DialogHeader><DialogTitle>{title}</DialogTitle></DialogHeader><nav className="grid gap-1 pt-3">{items.map((item) => <Link key={item.key} to={item.key} onClick={() => setOpen(false)} className={cn('flex items-center gap-3 rounded-md px-3 py-3 text-sm font-medium', pathname.startsWith(item.key) ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground')}>{item.icon}<span>{item.label}</span></Link>)}</nav></DialogContent></Dialog>
}
