import { useState, useRef, useEffect } from 'react'
import { DayPicker } from 'react-day-picker'
import { Calendar } from 'lucide-react'
import 'react-day-picker/dist/style.css'
import { format } from 'date-fns'

interface CalendarDatePickerProps {
  value?: string
  onChange: (date: string | undefined) => void
  placeholder?: string
  label?: string
  className?: string
}

export default function CalendarDatePicker({
  value,
  onChange,
  placeholder = 'Select date',
  label,
  className = ''
}: CalendarDatePickerProps) {
  const [isOpen, setIsOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const selectedDate = value ? new Date(value) : undefined

  // Close calendar when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isOpen])

  const handleSelect = (date: Date | undefined) => {
    if (date) {
      onChange(format(date, 'yyyy-MM-dd'))
    } else {
      onChange(undefined)
    }
  }

  return (
    <div className={`relative ${className}`} ref={containerRef}>
      {label && (
        <label className="block text-xs text-muted-foreground mb-1">
          {label}
        </label>
      )}
      <div className="relative">
        <button
          type="button"
          onClick={() => setIsOpen(!isOpen)}
          className={`w-full px-3 py-2 bg-background border border-border rounded-md text-sm text-foreground flex items-center justify-between hover:border-primary transition-colors ${
            isOpen ? 'border-primary ring-2 ring-primary/20' : ''
          }`}
        >
          <span className={selectedDate ? 'text-foreground' : 'text-muted-foreground'}>
            {selectedDate ? format(selectedDate, 'dd MMM yyyy') : placeholder}
          </span>
          <Calendar className="h-4 w-4 text-muted-foreground" />
        </button>

        {isOpen && (
          <div className="absolute z-50 mt-1 bg-card border border-border rounded-lg shadow-xl p-4 min-w-[280px]">
            <style>{`
              .rdp {
                --rdp-cell-size: 36px;
                --rdp-accent-color: hsl(var(--primary));
                --rdp-background-color: hsl(var(--secondary));
                --rdp-accent-color-dark: hsl(var(--primary));
                --rdp-background-color-dark: hsl(var(--secondary));
                --rdp-outline: 2px solid hsl(var(--primary));
                --rdp-outline-selected: 2px solid hsl(var(--primary));
                margin: 0;
              }
              
              .rdp-button {
                color: hsl(var(--foreground));
              }
              
              .rdp-button:hover:not([disabled]) {
                background-color: hsl(var(--secondary));
              }
              
              .rdp-day_selected {
                background-color: hsl(var(--primary));
                color: hsl(var(--background));
                font-weight: 600;
              }
              
              .rdp-day_today {
                font-weight: 600;
                border: 2px solid hsl(var(--primary));
              }
              
              .rdp-day_selected:hover {
                background-color: hsl(var(--primary) / 0.8);
              }
              
              .rdp-head_cell {
                color: hsl(var(--muted-foreground));
                font-weight: 500;
                font-size: 0.75rem;
              }
              
              .rdp-caption_label {
                color: hsl(var(--foreground));
                font-weight: 600;
                font-size: 0.875rem;
              }
              
              .rdp-nav_button {
                color: hsl(var(--foreground));
                background-color: hsl(var(--secondary));
                border: 1px solid hsl(var(--border));
              }
              
              .rdp-nav_button:hover {
                background-color: hsl(var(--secondary) / 0.8);
              }
              
              .rdp-day_outside {
                color: hsl(var(--muted-foreground));
                opacity: 0.5;
              }
              
              .rdp-day_disabled {
                opacity: 0.25;
                cursor: not-allowed;
              }
            `}</style>
            <DayPicker
              mode="single"
              selected={selectedDate}
              onSelect={handleSelect}
              modifiersClassNames={{
                selected: 'rdp-day_selected',
                today: 'rdp-day_today'
              }}
              classNames={{
                months: 'flex flex-col',
                month: 'space-y-4',
                caption: 'flex justify-center pt-1 relative items-center',
                caption_label: 'text-sm font-medium',
                nav: 'space-x-1 flex items-center',
                nav_button: 'h-7 w-7 bg-secondary border border-border rounded-md inline-flex items-center justify-center hover:bg-secondary/80',
                nav_button_previous: 'absolute left-1',
                nav_button_next: 'absolute right-1',
                table: 'w-full border-collapse space-y-1',
                head_row: 'flex',
                head_cell: 'text-muted-foreground rounded-md w-9 font-normal text-[0.8rem]',
                row: 'flex w-full mt-2',
                cell: 'text-center text-sm p-0 relative [&:has([aria-selected])]:bg-secondary first:[&:has([aria-selected])]:rounded-l-md last:[&:has([aria-selected])]:rounded-r-md focus-within:relative focus-within:z-20',
                day: 'h-9 w-9 p-0 font-normal aria-selected:opacity-100 rounded-md hover:bg-secondary',
                day_selected: 'bg-primary text-background hover:bg-primary hover:text-background focus:bg-primary focus:text-background',
                day_today: 'bg-secondary text-foreground font-semibold border-2 border-primary',
                day_outside: 'text-muted-foreground opacity-50',
                day_disabled: 'text-muted-foreground opacity-50',
                day_range_middle: 'aria-selected:bg-secondary aria-selected:text-foreground',
                day_hidden: 'invisible',
              }}
            />
            <div className="flex justify-end gap-2 mt-3 pt-3 border-t border-border">
              <button
                type="button"
                onClick={() => {
                  onChange(undefined)
                  setIsOpen(false)
                }}
                className="px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors rounded-md hover:bg-secondary"
              >
                Clear
              </button>
              <button
                type="button"
                onClick={() => setIsOpen(false)}
                className="px-3 py-1.5 text-xs bg-primary text-background rounded-md hover:bg-primary/90 transition-colors"
              >
                Done
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

