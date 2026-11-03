// Mock backend dùng chung qua localStorage: nhiều tab/cửa sổ cùng browser profile
// thấy cùng dữ liệu, nên kịch bản demo hai bàn chạy được khi chưa có FastAPI.
// ponytail: localStorage chỉ đồng bộ trong một browser profile; hai browser khác
// nhau cần backend thật (xem frontend/README.md).
import type {
  Bill, MenuItem, Order, OrderItem, Payment, Shift, Staff, Table, Ticket,
} from '../api/types'
import { ApiError } from '../api/types'

const KEY = 'taporder.db.v1'

interface Db {
  tables: Table[]
  menu: MenuItem[]
  bills: Bill[]
  payments: Payment[]
  shifts: Shift[]
  order_seq: number
}

const STAFF: Array<Staff & { password: string }> = [
  { id: 's1', username: 'barista', password: 'barista123', role: 'barista' },
  { id: 's2', username: 'cashier', password: 'cashier123', role: 'cashier' },
]

function seed(): Db {
  const rows: Array<[string, number, string]> = [
    ['Cà phê sữa', 30000, 'Cà phê'],
    ['Cà phê đen', 25000, 'Cà phê'],
    ['Bạc xỉu', 35000, 'Cà phê'],
    ['Trà đào', 35000, 'Trà'],
    ['Trà vải', 35000, 'Trà'],
    ['Trà sữa trân châu', 40000, 'Trà'],
    ['Bánh mì chảo', 45000, 'Đồ ăn'],
    ['Bánh flan', 20000, 'Đồ ăn'],
  ]
  const menu: MenuItem[] = rows.map(([name, unit_price_vnd, category], i) => ({
    id: `m${i + 1}`,
    name,
    unit_price_vnd,
    category,
    available: true,
    version: 1,
  }))
  const tables: Table[] = [1, 2, 3, 4, 5, 6].map((n) => ({
    number: n,
    qr_token: `t${n}`,
    status: 'free',
    bill_id: null,
    total_vnd: 0,
    can_pay: false,
  }))
  return { tables, menu, bills: [], payments: [], shifts: [], order_seq: 0 }
}

function read(): Db {
  try {
    const raw = localStorage.getItem(KEY)
    if (raw) return JSON.parse(raw) as Db
  } catch {
    // localStorage bị chặn: trả seed trong memory
  }
  const db = seed()
  write(db)
  return db
}

function write(db: Db) {
  try {
    localStorage.setItem(KEY, JSON.stringify(db))
  } catch {
    // không ghi được thì UI vẫn chạy với dữ liệu vừa tính
  }
}

function uid() {
  return Math.random().toString(36).slice(2, 10)
}

function allItems(bill: Bill): OrderItem[] {
  return bill.orders.flatMap((o) => o.items)
}

function recompute(db: Db, bill: Bill) {
  const live = allItems(bill).filter((i) => i.status !== 'cancelled')
  bill.total_vnd = live.reduce((s, i) => s + i.unit_price_vnd * i.quantity, 0)
  bill.can_pay =
    bill.status === 'open' &&
    allItems(bill).length > 0 &&
    live.every((i) => i.status === 'done')
  bill.version += 1
  const t = db.tables.find((x) => x.number === bill.table_number)
  if (!t) return
  if (bill.status === 'open') {
    t.status = 'serving'
    t.bill_id = bill.id
    t.total_vnd = bill.total_vnd
    t.can_pay = bill.can_pay
  } else {
    t.status = 'free'
    t.bill_id = null
    t.total_vnd = 0
    t.can_pay = false
  }
}

function openShift(db: Db): Shift | null {
  return db.shifts.find((s) => !s.closed_at) ?? null
}

function tableByToken(db: Db, token: string): Table {
  const t = db.tables.find((x) => x.qr_token === token)
  if (!t) throw new ApiError('QR_INVALID', 'Mã QR không hợp lệ.')
  return t
}

function openBillOf(db: Db, tableNumber: number): Bill | null {
  return db.bills.find((b) => b.table_number === tableNumber && b.status === 'open') ?? null
}

function billOr404(db: Db, id: string): Bill {
  const b = db.bills.find((x) => x.id === id)
  if (!b) throw new ApiError('NOT_FOUND', 'Không tìm thấy hóa đơn.')
  return b
}

export const mock = {
  // D02: mở QR chỉ resolve bàn, không tạo bill.
  guestBootstrap(qrToken: string) {
    const db = read()
    const t = tableByToken(db, qrToken)
    const bill = openBillOf(db, t.number)
    return { table_number: t.number, qr_token: t.qr_token, current_bill_id: bill ? bill.id : null }
  },

  menu(): MenuItem[] {
    return read().menu
  },

  shiftCurrent(): Shift | null {
    return openShift(read())
  },

  openShiftAction(): Shift {
    const db = read()
    if (openShift(db)) throw new ApiError('SHIFT_ALREADY_OPEN', 'Ca đang mở.')
    const s: Shift = { id: uid(), opened_at: new Date().toISOString(), closed_at: null }
    db.shifts.push(s)
    write(db)
    return s
  },

  closeShiftAction(id: string): Shift {
    const db = read()
    if (db.bills.some((b) => b.status === 'open')) {
      throw new ApiError('OPEN_BILLS_EXIST', 'Còn bàn chưa thanh toán, không đóng ca được.')
    }
    const s = db.shifts.find((x) => x.id === id)
    if (!s) throw new ApiError('NOT_FOUND', 'Không tìm thấy ca.')
    s.closed_at = new Date().toISOString()
    write(db)
    return s
  },

  // D03/D04: hết hàng hoặc lệch giá làm cả lượt gửi thất bại, giỏ giữ nguyên.
  submitOrder(
    qrToken: string,
    guestId: string,
    items: Array<{ menu_item_id: string; quantity: number; note: string; expected_unit_price_vnd: number }>,
  ): { bill_id: string; order_number: number } {
    const db = read()
    const t = tableByToken(db, qrToken)
    if (!openShift(db)) throw new ApiError('SHIFT_CLOSED', 'Quán chưa mở ca, chưa nhận order.')
    if (items.length === 0) throw new ApiError('EMPTY_CART', 'Giỏ đang trống.')

    const unavailable = items.filter((i) => {
      const m = db.menu.find((x) => x.id === i.menu_item_id)
      return !m || !m.available
    })
    if (unavailable.length > 0) {
      const names = unavailable.map((i) => {
        const m = db.menu.find((x) => x.id === i.menu_item_id)
        return m ? m.name : '?'
      })
      throw new ApiError('ITEM_UNAVAILABLE', `Món vừa hết hàng: ${names.join(', ')}. Vui lòng sửa giỏ.`, names)
    }
    const changed = items.filter((i) => {
      const m = db.menu.find((x) => x.id === i.menu_item_id)
      return !m || m.unit_price_vnd !== i.expected_unit_price_vnd
    })
    if (changed.length > 0) throw new ApiError('PRICE_CHANGED', 'Giá vừa thay đổi. Vui lòng xác nhận lại.')

    // D05: một bàn tối đa một bill open; gọi thêm gộp đúng bill đó.
    let bill = openBillOf(db, t.number)
    if (!bill) {
      bill = {
        id: uid(),
        table_number: t.number,
        status: 'open',
        version: 0,
        opened_at: new Date().toISOString(),
        paid_at: null,
        total_vnd: 0,
        can_pay: false,
        orders: [],
        payment: null,
      }
      db.bills.push(bill)
    }
    db.order_seq += 1
    const now = new Date().toISOString()
    const orderId = uid()
    const order: Order = {
      id: orderId,
      order_number: db.order_seq,
      bill_id: bill.id,
      created_at: now,
      items: items.map((i) => {
        const m = db.menu.find((x) => x.id === i.menu_item_id)
        if (!m) throw new ApiError('NOT_FOUND', 'Không tìm thấy món.')
        return {
          id: uid(),
          menu_item_id: m.id,
          name: m.name,
          unit_price_vnd: m.unit_price_vnd,
          quantity: i.quantity,
          note: i.note,
          status: 'waiting' as const,
          version: 1,
          guest_id: guestId,
          order_id: orderId,
          created_at: now,
        }
      }),
    }
    bill.orders.push(order)
    recompute(db, bill)
    write(db)
    return { bill_id: bill.id, order_number: order.order_number }
  },

  bill(id: string): Bill {
    return billOr404(read(), id)
  },

  // D01: khách chỉ hủy dòng của chính mình khi còn waiting.
  cancelItem(itemId: string, guestId: string): Bill {
    const db = read()
    for (const bill of db.bills) {
      for (const item of allItems(bill)) {
        if (item.id !== itemId) continue
        if (bill.status !== 'open') throw new ApiError('BILL_CLOSED', 'Hóa đơn đã thanh toán.')
        if (item.guest_id !== guestId) throw new ApiError('FORBIDDEN', 'Chỉ hủy được món bạn gọi.')
        if (item.status !== 'waiting') {
          throw new ApiError('STATE_CONFLICT', 'Món đã vào pha chế, không hủy được.')
        }
        item.status = 'cancelled'
        item.version += 1
        recompute(db, bill)
        write(db)
        return bill
      }
    }
    throw new ApiError('NOT_FOUND', 'Không tìm thấy món.')
  },

  // D08: FIFO theo created_at rồi tới id.
  kitchenQueue(): Ticket[] {
    const db = read()
    const tickets: Ticket[] = []
    for (const bill of db.bills) {
      if (bill.status !== 'open') continue
      for (const order of bill.orders) {
        for (const item of order.items) {
          if (item.status === 'done' || item.status === 'cancelled') continue
          tickets.push({
            item_id: item.id,
            table_number: bill.table_number,
            name: item.name,
            quantity: item.quantity,
            note: item.note,
            status: item.status,
            version: item.version,
            created_at: item.created_at,
            order_number: order.order_number,
          })
        }
      }
    }
    return tickets.sort((a, b) =>
      a.created_at === b.created_at
        ? a.item_id.localeCompare(b.item_id)
        : a.created_at.localeCompare(b.created_at),
    )
  },

  setItemStatus(itemId: string, status: 'preparing' | 'done'): void {
    const db = read()
    for (const bill of db.bills) {
      for (const item of allItems(bill)) {
        if (item.id !== itemId) continue
        const ok =
          (item.status === 'waiting' && status === 'preparing') ||
          (item.status === 'preparing' && status === 'done')
        if (!ok) throw new ApiError('INVALID_TRANSITION', `Không chuyển ${item.status} sang ${status}.`)
        item.status = status
        item.version += 1
        recompute(db, bill)
        write(db)
        return
      }
    }
    throw new ApiError('NOT_FOUND', 'Không tìm thấy món.')
  },

  toggleAvailability(menuItemId: string, available: boolean): MenuItem {
    const db = read()
    const m = db.menu.find((x) => x.id === menuItemId)
    if (!m) throw new ApiError('NOT_FOUND', 'Không tìm thấy món.')
    m.available = available
    m.version += 1
    write(db)
    return m
  },

  cashierTables(): Table[] {
    return read().tables
  },

  // D06/D07: chỉ thu khi mọi món đã xong; một payment duy nhất, không mở lại bill.
  pay(billId: string, expectedTotal: number): Payment {
    const db = read()
    const bill = billOr404(db, billId)
    const shift = openShift(db)
    if (!shift) throw new ApiError('SHIFT_CLOSED', 'Chưa mở ca.')
    if (bill.status === 'paid') throw new ApiError('BILL_CLOSED', 'Hóa đơn đã thanh toán.')
    if (!bill.can_pay) throw new ApiError('ITEMS_NOT_DONE', 'Còn món chưa xong, chưa thu được tiền.')
    if (bill.total_vnd !== expectedTotal) throw new ApiError('AMOUNT_CHANGED', 'Tổng tiền vừa thay đổi. Tải lại.')
    const payment: Payment = {
      id: uid(),
      bill_id: bill.id,
      shift_id: shift.id,
      amount_vnd: bill.total_vnd,
      method: 'cash',
      paid_at: new Date().toISOString(),
    }
    bill.status = 'paid'
    bill.paid_at = payment.paid_at
    bill.payment = payment
    db.payments.push(payment)
    recompute(db, bill)
    write(db)
    return payment
  },

  shiftReport(): { revenue_vnd: number; paid_bill_count: number; top_items: Array<{ name: string; quantity: number }> } {
    const db = read()
    const shift = openShift(db)
    const payments = shift ? db.payments.filter((p) => p.shift_id === shift.id) : []
    const counts = new Map<string, number>()
    for (const p of payments) {
      const bill = db.bills.find((b) => b.id === p.bill_id)
      if (!bill) continue
      for (const i of allItems(bill)) {
        if (i.status === 'cancelled') continue
        counts.set(i.name, (counts.get(i.name) ?? 0) + i.quantity)
      }
    }
    return {
      revenue_vnd: payments.reduce((s, p) => s + p.amount_vnd, 0),
      paid_bill_count: payments.length,
      top_items: [...counts.entries()]
        .map(([name, quantity]) => ({ name, quantity }))
        .sort((a, b) => b.quantity - a.quantity)
        .slice(0, 5),
    }
  },

  login(username: string, password: string): Staff {
    const s = STAFF.find((x) => x.username === username && x.password === password)
    if (!s) throw new ApiError('INVALID_CREDENTIALS', 'Sai tài khoản hoặc mật khẩu.')
    return { id: s.id, username: s.username, role: s.role }
  },

  reset(): void {
    write(seed())
  },
}
