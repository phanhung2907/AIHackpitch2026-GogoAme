// Một API client duy nhất cho cả ba giao diện. Khi VITE_USE_MOCK=1 các hàm chạy
// trên mock store trong browser; khi tắt, cùng chữ ký đó gọi FastAPI theo contract
// trong plans/product-plan.md §10.2, nên UI không phải sửa khi backend sẵn sàng.
import type { Bill, MenuItem, Payment, Shift, Staff, Table, Ticket } from './types'
import { ApiError } from './types'
import { mock } from '../mocks/store'

const USE_MOCK = import.meta.env.VITE_USE_MOCK !== '0'
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

function newIdempotencyKey(): string {
  return crypto.randomUUID()
}

async function http<T>(path: string, init?: RequestInit & { idempotent?: boolean }): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...((init?.headers as Record<string, string>) ?? {}),
  }
  if (init?.method && init.method !== 'GET') {
    if (csrfToken) headers['X-CSRF-Token'] = csrfToken
    if (init.idempotent) headers['Idempotency-Key'] = newIdempotencyKey()
  }
  const res = await fetch(`${BASE}${path}`, { ...init, credentials: 'same-origin', headers })
  const body = await res.json().catch(() => null)
  if (!res.ok) {
    const err = body?.error
    throw new ApiError(err?.code ?? 'HTTP_ERROR', err?.message ?? `Lỗi ${res.status}`, err?.details ?? null)
  }
  if (body?.data?.csrf_token) csrfToken = body.data.csrf_token
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
    return http<{ table_number: number; qr_token: string; current_bill_id: string | null }>('/guest/bootstrap', {
      method: 'POST',
      body: JSON.stringify({ qr_token: qrToken }),
    })
  },

  async menu(): Promise<MenuItem[]> {
    if (USE_MOCK) return mock.menu()
    const d = await http<{ items: any[] }>('/guest/menu')
    return (d.items ?? []).map((i) => ({ ...i, unit_price_vnd: money(i.unit_price_vnd) }))
  },

  async submitOrder(qrToken: string, items: CartLine[]) {
    if (USE_MOCK) return mock.submitOrder(qrToken, guestId(), items)
    const d = await http<{ bill: any; order: any }>('/guest/orders', {
      method: 'POST',
      idempotent: true,
      body: JSON.stringify({
        qr_token: qrToken,
        expected_bill_id: null,
        items: items.map((i) => ({ ...i, expected_unit_price_vnd: String(i.expected_unit_price_vnd) })),
      }),
    })
    return { bill_id: d.bill.id as string, order_number: d.order.order_number as number }
  },

  async bill(id: string): Promise<Bill> {
    if (USE_MOCK) return mock.bill(id)
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
    return Array.isArray(d) ? d : (d.tickets ?? [])
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
    return rows.map((t: any) => ({ ...t, total_vnd: money(t.total_vnd) }))
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
    return http<Shift | null>('/cashier/shifts/current')
  },

  async openShift(): Promise<Shift> {
    if (USE_MOCK) return mock.openShiftAction()
    return http<Shift>('/cashier/shifts', { method: 'POST', idempotent: true, body: JSON.stringify({}) })
  },

  async closeShift(id: string, expectedVersion: number): Promise<Shift> {
    if (USE_MOCK) return mock.closeShiftAction(id)
    return http<Shift>(`/cashier/shifts/${id}/close`, {
      method: 'POST',
      idempotent: true,
      body: JSON.stringify({ expected_version: expectedVersion }),
    })
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
      item: { ...r.item, unit_price_vnd: money(r.item.unit_price_vnd) },
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

  async logout() {
    if (USE_MOCK) return
    await http<void>('/auth/logout', { method: 'POST', body: JSON.stringify({}) })
    csrfToken = null
  },

  resetDemo() {
    if (USE_MOCK) mock.reset()
  },
}
