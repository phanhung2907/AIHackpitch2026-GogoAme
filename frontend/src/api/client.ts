// Một API client duy nhất cho cả ba giao diện. Khi VITE_USE_MOCK=1 các hàm chạy
// trên mock store trong browser; khi tắt, cùng chữ ký đó gọi FastAPI theo contract
// trong plans/product-plan.md §10.2, nên UI không phải sửa khi backend sẵn sàng.
import type { Bill, MenuItem, Payment, Shift, Staff, Table, Ticket } from './types'
import { ApiError } from './types'
import { mock } from '../mocks/store'

const USE_MOCK = import.meta.env.VITE_USE_MOCK !== '0'
const BASE = import.meta.env.VITE_API_BASE ?? '/api/v1'

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  })
  const body = await res.json().catch(() => null)
  if (!res.ok) {
    const err = body?.error
    throw new ApiError(err?.code ?? 'HTTP_ERROR', err?.message ?? `Lỗi ${res.status}`, err?.details ?? null)
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
  guestBootstrap(qrToken: string) {
    if (USE_MOCK) return Promise.resolve(mock.guestBootstrap(qrToken))
    return http<{ table_number: number; qr_token: string; current_bill_id: string | null }>('/guest/bootstrap', {
      method: 'POST',
      body: JSON.stringify({ qr_token: qrToken }),
    })
  },

  menu(): Promise<MenuItem[]> {
    if (USE_MOCK) return Promise.resolve(mock.menu())
    return http<MenuItem[]>('/guest/menu')
  },

  submitOrder(qrToken: string, items: CartLine[]) {
    if (USE_MOCK) return Promise.resolve(mock.submitOrder(qrToken, guestId(), items))
    return http<{ bill_id: string; order_number: number }>('/guest/orders', {
      method: 'POST',
      body: JSON.stringify({ qr_token: qrToken, expected_bill_id: null, items }),
    })
  },

  bill(id: string): Promise<Bill> {
    if (USE_MOCK) return Promise.resolve(mock.bill(id))
    return http<Bill>(`/guest/bills/${id}`)
  },

  cancelItem(itemId: string) {
    if (USE_MOCK) return Promise.resolve(mock.cancelItem(itemId, guestId()))
    return http<Bill>(`/guest/items/${itemId}/cancel`, { method: 'POST', body: JSON.stringify({}) })
  },

  kitchenQueue(): Promise<Ticket[]> {
    if (USE_MOCK) return Promise.resolve(mock.kitchenQueue())
    return http<Ticket[]>('/kitchen/queue')
  },

  setItemStatus(itemId: string, status: 'preparing' | 'done') {
    if (USE_MOCK) return Promise.resolve(mock.setItemStatus(itemId, status))
    return http<void>(`/kitchen/items/${itemId}/status`, { method: 'PATCH', body: JSON.stringify({ status }) })
  },

  kitchenMenu(): Promise<MenuItem[]> {
    if (USE_MOCK) return Promise.resolve(mock.menu())
    return http<MenuItem[]>('/kitchen/menu')
  },

  setAvailability(id: string, available: boolean) {
    if (USE_MOCK) return Promise.resolve(mock.toggleAvailability(id, available))
    return http<MenuItem>(`/kitchen/menu/${id}/availability`, {
      method: 'PATCH',
      body: JSON.stringify({ available }),
    })
  },

  tables(): Promise<Table[]> {
    if (USE_MOCK) return Promise.resolve(mock.cashierTables())
    return http<Table[]>('/cashier/tables')
  },

  cashierBill(id: string): Promise<Bill> {
    if (USE_MOCK) return Promise.resolve(mock.bill(id))
    return http<Bill>(`/cashier/bills/${id}`)
  },

  pay(billId: string, expectedTotal: number): Promise<Payment> {
    if (USE_MOCK) return Promise.resolve(mock.pay(billId, expectedTotal))
    return http<Payment>(`/cashier/bills/${billId}/payments`, {
      method: 'POST',
      body: JSON.stringify({ expected_total_vnd: String(expectedTotal), method: 'cash' }),
    })
  },

  shiftCurrent(): Promise<Shift | null> {
    if (USE_MOCK) return Promise.resolve(mock.shiftCurrent())
    return http<Shift | null>('/cashier/shifts/current')
  },

  openShift(): Promise<Shift> {
    if (USE_MOCK) return Promise.resolve(mock.openShiftAction())
    return http<Shift>('/cashier/shifts', { method: 'POST', body: JSON.stringify({}) })
  },

  closeShift(id: string): Promise<Shift> {
    if (USE_MOCK) return Promise.resolve(mock.closeShiftAction(id))
    return http<Shift>(`/cashier/shifts/${id}/close`, { method: 'POST', body: JSON.stringify({}) })
  },

  shiftReport() {
    if (USE_MOCK) return Promise.resolve(mock.shiftReport())
    return http<{ revenue_vnd: number; paid_bill_count: number; top_items: Array<{ name: string; quantity: number }> }>(
      '/cashier/shifts/current/report',
    )
  },

  login(username: string, password: string): Promise<Staff> {
    if (USE_MOCK) return Promise.resolve(mock.login(username, password))
    return http<Staff>('/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) })
  },

  resetDemo() {
    if (USE_MOCK) mock.reset()
  },
}
