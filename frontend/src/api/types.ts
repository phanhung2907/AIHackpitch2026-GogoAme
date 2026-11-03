export type ItemStatus = 'waiting' | 'preparing' | 'done' | 'cancelled'
export type BillStatus = 'open' | 'paid'

export interface MenuItem {
  id: string
  category: string
  name: string
  unit_price_vnd: number
  available: boolean
  version: number
}

export interface OrderItem {
  id: string
  menu_item_id: string
  name: string
  unit_price_vnd: number
  quantity: number
  note: string
  status: ItemStatus
  version: number
  guest_id: string
  order_id: string
  created_at: string
}

export interface Order {
  id: string
  order_number: number
  bill_id: string
  created_at: string
  items: OrderItem[]
}

export interface Bill {
  id: string
  table_number: number
  status: BillStatus
  version: number
  opened_at: string
  paid_at: string | null
  total_vnd: number
  can_pay: boolean
  orders: Order[]
  payment: Payment | null
}

export interface Payment {
  id: string
  bill_id: string
  shift_id: string
  amount_vnd: number
  method: 'cash'
  paid_at: string
}

export interface Table {
  number: number
  qr_token: string
  status: 'free' | 'serving'
  bill_id: string | null
  total_vnd: number
  can_pay: boolean
}

export interface Shift {
  id: string
  opened_at: string
  closed_at: string | null
  version: number
}

export interface Ticket {
  item_id: string
  table_number: number
  name: string
  quantity: number
  note: string
  status: ItemStatus
  version: number
  created_at: string
  order_number: number
}

export interface Staff {
  id: string
  username: string
  role: 'barista' | 'cashier'
}

export class ApiError extends Error {
  code: string
  details: unknown
  constructor(code: string, message: string, details: unknown = null) {
    super(message)
    this.code = code
    this.details = details
  }
}
