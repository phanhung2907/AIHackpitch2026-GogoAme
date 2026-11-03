// Một API client duy nhất cho cả ba giao diện. Khi VITE_USE_MOCK=1 các hàm chạy
// trên mock store trong browser; khi tắt, cùng chữ ký đó gọi FastAPI theo contract
// trong plans/product-plan.md §10.2, nên UI không phải sửa khi backend sẵn sàng.
import type { Bill, MenuItem, Payment, Shift, Staff, Table, Ticket } from './types'
import { ApiError } from './types'
import { mock } from '../mocks/store'

const USE_MOCK = import.meta.env.VITE_USE_MOCK === '1'
const BASE = import.meta.env.VITE_API_BASE ?? '/api/v1'

export const usingMock = USE_MOCK

/** Contract §10.1 truyền tiền VND dưới dạng chuỗi decimal; UI tính bằng integer. */
function money(v: unknown): number {
  return typeof v === 'string' ? Number(v) : typeof v === 'number' ? v : 0
}

function normalizeBill(b: any): Bill {
  return {
    ...b,
    total_vnd: money(b.total_vnd),
    orders: (b.orders ?? []).map((o: any) => ({
      ...o,
      items: (o.items ?? []).map((i: any) => ({ ...i, unit_price_vnd: money(i.unit_price_vnd) })),
    })),
    payment: b.payment ? { ...b.payment, amount_vnd: money(b.payment.amount_vnd) } : null,
  }
}

/** CSRF token giữ trong memory, không localStorage (plan §4.1). */
let csrfToken: string | null = null
let staffCsrf: string | null = null
let guestCsrf: string | null = null
const visits = new Map<string, string | null>()
const categories = new Map<string, string>()
const pendingKeys = new Map<string, string>()
function menuItem(i: any): MenuItem {
  return { ...i, category: i.category ?? categories.get(i.category_id) ?? 'Thực đơn', unit_price_vnd: money(i.price_vnd ?? i.unit_price_vnd) }
}

function newIdempotencyKey(): string {
  if (crypto.randomUUID) return crypto.randomUUID()
  const bytes = crypto.getRandomValues(new Uint8Array(16))
  bytes[6] = (bytes[6] & 15) | 64
  bytes[8] = (bytes[8] & 63) | 128
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('')
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
}

async function http<T>(path: string, init?: RequestInit & { idempotent?: boolean }): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...((init?.headers as Record<string, string>) ?? {}),
  }
  if (init?.method && init.method !== 'GET') {
    const token = path.startsWith('/guest/') ? guestCsrf : staffCsrf ?? csrfToken
    if (token) headers['X-CSRF-Token'] = token
    if (init.idempotent) {
      const command = `${path}:${init.body ?? ''}`
      if (!pendingKeys.has(command)) pendingKeys.set(command, newIdempotencyKey())
      headers['Idempotency-Key'] = pendingKeys.get(command)!
    }
  }
  const res = await fetch(`${BASE}${path}`, { ...init, credentials: 'same-origin', headers })
  const body = await res.json().catch(() => null)
  if (res.ok || (res.status >= 400 && res.status < 500)) pendingKeys.delete(`${path}:${init?.body ?? ''}`)
  if (!res.ok) {
    const err = body?.error
    throw new ApiError(err?.code ?? 'HTTP_ERROR', err?.message ?? `Lỗi ${res.status}`, err?.details ?? null)
  }
  if (body?.data?.csrf_token) {
    csrfToken = body.data.csrf_token
    if (path.startsWith('/guest/')) guestCsrf = csrfToken
    else staffCsrf = csrfToken
  }
  return body?.data as T
}

/** Phiên khách ẩn danh. Mock giữ trong sessionStorage; backend thật dùng cookie HttpOnly. */
export function guestId(): string {
  const k = 'taporder.guest'
  let v = sessionStorage.getItem(k)
  if (!v) {
    v = Math.random().toString(36).slice(2, 10)
    sessionStorage.setItem(k, v)
  }
  return v
}

export interface CartLine {
  menu_item_id: string
  quantity: number
  note: string
  expected_unit_price_vnd: number
}

export const api = {
  async guestBootstrap(qrToken: string) {
    if (USE_MOCK) return mock.guestBootstrap(qrToken)
    const d = await http<any>('/guest/bootstrap', {
      method: 'POST',
      body: JSON.stringify({ qr_token: qrToken }),
    })
    visits.set(qrToken, d.current_bill_id)
    sessionStorage.setItem('taporder.qr', qrToken)
    if (d.current_bill_id) await http('/guest/join', { method: 'POST', body: JSON.stringify({ qr_token: qrToken, expected_bill_id: d.current_bill_id }) })
    return { ...d, table_number: d.table.number, qr_token: qrToken }
  },

  async menu(): Promise<MenuItem[]> {
    if (USE_MOCK) return mock.menu()
    const d = await http<{ items: any[]; categories: any[] }>('/guest/menu')
    for (const c of d.categories ?? []) categories.set(c.id, c.name)
    return (d.items ?? []).map(menuItem)
  },

  async submitOrder(qrToken: string, items: CartLine[]) {
    if (USE_MOCK) return mock.submitOrder(qrToken, guestId(), items)
    const d = await http<{ bill: any; order: any }>('/guest/orders', {
      method: 'POST',
      idempotent: true,
      body: JSON.stringify({
        qr_token: qrToken,
        expected_bill_id: visits.get(qrToken) ?? null,
        items: items.map((i) => ({ ...i, expected_unit_price_vnd: String(i.expected_unit_price_vnd) })),
      }),
    })
    visits.set(qrToken, d.bill.id)
    return { bill_id: d.bill.id as string, order_number: d.order.order_number as number }
  },

  async bill(id: string): Promise<Bill> {
    if (USE_MOCK) return mock.bill(id)
    if (!guestCsrf) { const qr = sessionStorage.getItem('taporder.qr'); if (qr) await api.guestBootstrap(qr) }
    return normalizeBill(await http<any>(`/guest/bills/${id}`))
  },

  async cancelItem(itemId: string, expectedVersion: number) {
    if (USE_MOCK) return mock.cancelItem(itemId, guestId(), expectedVersion)
    return http<any>(`/guest/items/${itemId}/cancel`, {
      method: 'POST',
      idempotent: true,
      body: JSON.stringify({ expected_version: expectedVersion }),
    })
  },

  async kitchenQueue(): Promise<Ticket[]> {
    if (USE_MOCK) return mock.kitchenQueue()
    const d = await http<{ tickets?: Ticket[] } | Ticket[]>('/kitchen/queue')
    const orders: any[] = Array.isArray(d) ? d : (d.tickets ?? [])
    return orders.flatMap((o: any) => o.items ? o.items.filter((i: any) => i.status === 'waiting' || i.status === 'preparing').map((i: any) => ({ ...i, item_id: i.id, table_number: o.table.number, created_at: o.created_at, order_number: Number(o.order_number) })) : [o])
  },

  async setItemStatus(itemId: string, status: 'preparing' | 'done', expectedVersion: number) {
    if (USE_MOCK) return mock.setItemStatus(itemId, status, expectedVersion)
    return http<void>(`/kitchen/items/${itemId}/status`, {
      method: 'PATCH',
      idempotent: true,
      body: JSON.stringify({ status, expected_version: expectedVersion }),
    })
  },

  async kitchenMenu(): Promise<MenuItem[]> {
    if (USE_MOCK) return mock.menu()
    const d = await http<{ items: any[] } | any[]>('/kitchen/menu')
    const items = Array.isArray(d) ? d : (d.items ?? [])
    // Projection pha chế không có giá (plan §4.2); để 0 cho UI không hiện tiền.
    return items.map((i: any) => ({ ...i, unit_price_vnd: money(i.unit_price_vnd) }))
  },

  async setAvailability(id: string, available: boolean, expectedVersion: number) {
    if (USE_MOCK) return mock.toggleAvailability(id, available, expectedVersion)
    return http<MenuItem>(`/kitchen/menu/${id}/availability`, {
      method: 'PATCH',
      idempotent: true,
      body: JSON.stringify({ available, expected_version: expectedVersion }),
    })
  },

  async tables(): Promise<Table[]> {
    if (USE_MOCK) return mock.cashierTables()
    const d = await http<{ tables: any[] } | any[]>('/cashier/tables')
    const rows = Array.isArray(d) ? d : (d.tables ?? [])
    return rows.map((t: any) => ({ ...t, status: t.status === 'ready_to_pay' ? 'serving' : t.status, total_vnd: money(t.total_vnd) }))
  },

  async cashierBill(id: string): Promise<Bill> {
    if (USE_MOCK) return mock.bill(id)
    return normalizeBill(await http<any>(`/cashier/bills/${id}`))
  },

  async pay(billId: string, expectedTotal: number, expectedBillVersion: number): Promise<Payment> {
    if (USE_MOCK) return mock.pay(billId, expectedTotal, expectedBillVersion)
    const d = await http<{ payment: any }>(`/cashier/bills/${billId}/payments`, {
      method: 'POST',
      idempotent: true,
      body: JSON.stringify({
        expected_bill_version: expectedBillVersion,
        expected_total_vnd: String(expectedTotal),
        method: 'cash',
      }),
    })
    return { ...d.payment, amount_vnd: money(d.payment.amount_vnd) }
  },

  async shiftCurrent(): Promise<Shift | null> {
    if (USE_MOCK) return mock.shiftCurrent()
    return (await http<{shift: Shift | null}>('/cashier/shifts/current')).shift
  },

  async openShift(): Promise<Shift> {
    if (USE_MOCK) return mock.openShiftAction()
    return (await http<{shift: Shift}>('/cashier/shifts', { method: 'POST', idempotent: true, body: JSON.stringify({}) })).shift
  },

  async closeShift(id: string, expectedVersion: number): Promise<Shift> {
    if (USE_MOCK) return mock.closeShiftAction(id)
    return (await http<{shift: Shift}>(`/cashier/shifts/${id}/close`, {
      method: 'POST',
      idempotent: true,
      body: JSON.stringify({ expected_version: expectedVersion }),
    })).shift
  },

  async shiftReport(shiftId: string | null) {
    if (USE_MOCK) return mock.shiftReport()
    if (!shiftId) return { revenue_vnd: 0, paid_bill_count: 0, top_items: [] }
    const d = await http<any>(`/cashier/shifts/${shiftId}/report`)
    return {
      revenue_vnd: money(d.revenue_vnd),
      paid_bill_count: d.paid_bill_count as number,
      top_items: (d.top_items ?? []) as Array<{ name: string; quantity: number }>,
    }
  },

  /** F11 (P2): tối đa 3 món còn hàng, gợi ý theo giờ quán rồi tới món bán chạy. */
  async recommendations(): Promise<Array<{ item: MenuItem; reason: string }>> {
    if (USE_MOCK) return mock.recommendations()
    const d = await http<{ items: any[] }>('/guest/recommendations')
    return (d.items ?? []).map((r: any) => ({
      item: menuItem(r.item),
      reason: r.reason as string,
    }))
  },

  async login(username: string, password: string): Promise<Staff> {
    if (USE_MOCK) return mock.login(username, password)
    await http<{ csrf_token: string }>('/auth/bootstrap')
    const d = await http<{ staff: Staff; csrf_token: string }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    })
    return d.staff
  },

  async session(): Promise<Staff | null> {
    if (USE_MOCK) return null
    return (await http<{staff: Staff}>('/auth/session')).staff
  },

  async tableQr(table: Table): Promise<string> {
    if (USE_MOCK) return `${window.location.origin}/t/${table.qr_token}`
    return (await http<{url: string}>(`/cashier/tables/${table.id}/qr`)).url
  },

  async logout() {
    if (USE_MOCK) return
    await http<void>('/auth/logout', { method: 'POST', body: JSON.stringify({}) })
    csrfToken = null
  },

  resetDemo() {
    if (USE_MOCK) mock.reset()
  },
}
