import { useEffect, useState } from 'react'
import { usingMock } from '../api/client'

/**
 * F09 ở bản chưa có SSE: polling là nguồn cập nhật duy nhất, nên UI phải nói rõ
 * đang đồng bộ kiểu gì và lần làm mới gần nhất là khi nào. Khi backend có
 * /events, mở stream và truyền `live` = stream đang mở, giữ nguyên badge này.
 */
export function useOnline(): boolean {
  const [online, setOnline] = useState(() => navigator.onLine)
  useEffect(() => {
    const up = () => setOnline(true)
    const down = () => setOnline(false)
    window.addEventListener('online', up)
    window.addEventListener('offline', down)
    return () => {
      window.removeEventListener('online', up)
      window.removeEventListener('offline', down)
    }
  }, [])
  return online
}

export function SyncBadge({ updatedAt, intervalMs }: { updatedAt: number; intervalMs: number }) {
  const online = useOnline()
  const [, tick] = useState(0)

  // Cho badge tự già đi để người xem thấy khi dữ liệu đứng im.
  useEffect(() => {
    const t = setInterval(() => tick((n) => n + 1), 1000)
    return () => clearInterval(t)
  }, [])

  const ageMs = updatedAt ? Date.now() - updatedAt : 0
  const stale = !online || ageMs > intervalMs * 3
  const label = !online
    ? 'Mất kết nối'
    : !updatedAt
      ? 'Đang tải'
      : stale
        ? `Chậm ${Math.round(ageMs / 1000)}s`
        : `Đồng bộ ${Math.round(ageMs / 1000)}s trước`

  return (
    <span
      role="status"
      aria-live="polite"
      className={
        'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ' +
        (stale ? 'bg-amber-100 text-amber-800' : 'bg-emerald-100 text-emerald-700')
      }
    >
      <span className={'h-1.5 w-1.5 rounded-full ' + (stale ? 'bg-amber-500' : 'bg-emerald-500')} />
      {label}
      {usingMock && <span className="opacity-60">· mock</span>}
    </span>
  )
}

/** Mất mạng thì giãn polling về 5 giây theo plan §3.3, có mạng thì giữ nhịp nhanh. */
export function pollInterval(online: boolean, fastMs: number): number {
  return online ? fastMs : 5000
}
