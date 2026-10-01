import type { ReactNode } from 'react'
import { Search, X } from 'lucide-react'

export function Field({
  label,
  value,
  onChange,
  options,
  placeholder = 'All',
}: {
  label: string
  value: string
  onChange: (value: string) => void
  options?: string[]
  placeholder?: string
}) {
  return (
    <label className="field">
      <span>{label}</span>
      {options ? (
        <select value={value} onChange={(e) => onChange(e.target.value)}>
          <option value="">{placeholder}</option>
          {options.map((v) => (
            <option key={v}>{v}</option>
          ))}
        </select>
      ) : (
        <div className="search-input">
          <Search size={15} />
          <input
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder={placeholder}
          />
          {value && (
            <button onClick={() => onChange('')} aria-label={`Clear ${label}`}>
              <X size={14} />
            </button>
          )}
        </div>
      )}
    </label>
  )
}

export function FilterBar({ children, onReset }: { children: ReactNode; onReset?: () => void }) {
  return (
    <div className="filter-bar">
      {children}
      {onReset && (
        <button className="button button-quiet filter-reset" onClick={onReset}>
          <X size={15} />
          Reset
        </button>
      )}
    </div>
  )
}

export function Segmented({
  value,
  options,
  onChange,
  label,
}: {
  value: string
  options: string[]
  onChange: (value: string) => void
  label: string
}) {
  return (
    <div className="segmented" role="group" aria-label={label}>
      {options.map((option) => (
        <button
          key={option}
          className={value === option ? 'active' : ''}
          onClick={() => onChange(option)}
        >
          {option}
        </button>
      ))}
    </div>
  )
}
