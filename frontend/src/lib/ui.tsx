import clsx from 'clsx'
import type { ButtonHTMLAttributes, ReactNode } from 'react'
import type { ItemStatus } from '../api/types'

export function vnd(amount: number): string {
  return new Intl.NumberFormat('vi-VN').format(amount) + ' đ'
}

export function clock(iso: string): string {
  return new Date(iso).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })
}

type Variant = 'primary' | 'secondary' | 'danger' | 'ghost'

const VARIANTS: Record<Variant, string> = {
  primary: 'bg-amber-600 text-white hover:bg-amber-700',
  secondary: 'bg-white text-slate-900 border border-slate-300 hover:bg-slate-50',
  danger: 'bg-white text-red-600 border border-red-300 hover:bg-red-50',
  ghost: 'text-slate-600 hover:bg-slate-100',
}

export function Button({
  variant = 'primary',
  className,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      {...rest}
      className={clsx(
        'min-h-[44px] rounded-lg px-4 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50',
        VARIANTS[variant],
        className,
      )}
    />
  )
}

export function Card({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={clsx('rounded-xl border border-slate-200 bg-white p-4 shadow-sm', className)}>{children}</div>
}

const STATUS_LABEL: Record<ItemStatus, string> = {
  waiting: 'Chờ',
  preparing: 'Đang pha',
  done: 'Xong',
  cancelled: 'Đã hủy',
}

const STATUS_STYLE: Record<ItemStatus, string> = {
  waiting: 'bg-slate-100 text-slate-700',
  preparing: 'bg-blue-100 text-blue-700',
  done: 'bg-emerald-100 text-emerald-700',
  cancelled: 'bg-red-50 text-red-600 line-through',
}

export function StatusBadge({ status }: { status: ItemStatus }) {
  return (
    <span className={clsx('rounded-full px-2.5 py-1 text-xs font-semibold', STATUS_STYLE[status])}>
      {STATUS_LABEL[status]}
    </span>
  )
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700" role="alert">
      <p>{message}</p>
      {onRetry && (
        <button onClick={onRetry} className="mt-2 font-semibold underline">
          Thử lại
        </button>
      )}
    </div>
  )
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="py-10 text-center text-sm text-slate-500">{children}</p>
}
