// AUTO-GENERATED FROM contracts/openapi.yaml (CONTRACT-1) — DO NOT EDIT MANUALLY
export const CONTRACT_REVISION = 'CONTRACT-1' as const;

export type StaffRole = "barista" | "cashier";

export type BillStatus = "open" | "paid";

export type ShiftStatus = "open" | "closed";

export type OrderItemStatus = "waiting" | "preparing" | "done" | "cancelled";

export type KitchenTargetStatus = "preparing" | "done";

export type TableDerivedStatus = "free" | "serving" | "ready_to_pay";

export type PaymentMethod = "cash";

export type RecommendationReason = "time_of_day" | "bestseller" | "seed_order";

export type SseEventType = "order.created" | "item.updated" | "bill.updated" | "bill.closed" | "menu.updated" | "shift.updated" | "checkpoint" | "reset" | "session_expired";

export type ErrorCode = "SESSION_EXPIRED" | "INVALID_CREDENTIALS" | "FORBIDDEN" | "CSRF_INVALID" | "ORIGIN_INVALID" | "NOT_FOUND" | "TABLE_VISIT_CHANGED" | "BILL_CLOSED" | "SHIFT_CLOSED" | "SHIFT_ALREADY_OPEN" | "OPEN_BILLS_EXIST" | "ITEM_UNAVAILABLE" | "PRICE_CHANGED" | "VERSION_CONFLICT" | "STATE_CONFLICT" | "INVALID_TRANSITION" | "ITEMS_NOT_DONE" | "AMOUNT_CHANGED" | "IDEMPOTENCY_CONFLICT" | "VALIDATION_ERROR" | "BILL_LIMIT_EXCEEDED" | "INVALID_CURSOR" | "RATE_LIMITED" | "RETRYABLE_CONFLICT" | "SERVICE_UNAVAILABLE" | "PAYLOAD_TOO_LARGE" | "INTERNAL_ERROR";

export type MoneyVndString = string;

export type PositiveMoneyVndString = string;

export type CursorString = string;

export type QrTokenString = string;

export interface ErrorObject {
  code: ErrorCode;
  message: string;
  details: Record<string, unknown>;
  request_id: string;
}

export interface ErrorEnvelope {
  error: ErrorObject;
}

export interface PaginationMeta {
  next_cursor: string | null;
  limit: number;
}

export interface LoginInput {
  username: string;
  password: string;
}

export interface BootstrapGuestInput {
  qr_token: QrTokenString;
}

export interface JoinInput {
  qr_token: QrTokenString;
  expected_bill_id: string | null;
}

export interface OrderLineInput {
  menu_item_id: string;
  quantity: number;
  note?: string;
  expected_unit_price_vnd: PositiveMoneyVndString;
}

export interface OrderInput {
  qr_token: QrTokenString;
  expected_bill_id: string | null;
  items: Array<OrderLineInput>;
}

export interface ItemVersionInput {
  expected_version: number;
}

export interface ItemStatusInput {
  expected_version: number;
  status: KitchenTargetStatus;
}

export interface AvailabilityInput {
  expected_version: number;
  available: boolean;
}

export interface PaymentInput {
  expected_bill_version: number;
  expected_total_vnd: MoneyVndString;
  method: PaymentMethod;
}

export type OpenShiftInput = Record<string, never>;

export interface CloseShiftInput {
  expected_version: number;
}

export interface StaffDTO {
  id: string;
  username: string;
  role: StaffRole;
}

export interface TableRefDTO {
  id: string;
  number: number;
  label: string;
}

export interface CategoryDTO {
  id: string;
  name: string;
  sort_order: number;
}

export interface GuestMenuItemDTO {
  id: string;
  category_id: string;
  name: string;
  description: string;
  price_vnd: PositiveMoneyVndString;
  available: boolean;
  version: number;
  sort_order: number;
}

export interface KitchenMenuItemDTO {
  id: string;
  category_id: string;
  name: string;
  available: boolean;
  version: number;
  sort_order: number;
}

export interface GuestItemDTO {
  id: string;
  menu_item_id: string;
  name: string;
  unit_price_vnd: PositiveMoneyVndString;
  quantity: number;
  note: string;
  status: OrderItemStatus;
  version: number;
  is_mine: boolean;
  can_cancel: boolean;
}

export interface CashierItemDTO {
  id: string;
  menu_item_id: string;
  name: string;
  unit_price_vnd: PositiveMoneyVndString;
  quantity: number;
  note: string;
  status: OrderItemStatus;
  version: number;
}

export interface KitchenItemDTO {
  id: string;
  menu_item_id: string;
  name: string;
  quantity: number;
  note: string;
  status: OrderItemStatus;
  version: number;
  started_at: string | null;
}

export interface GuestOrderDTO {
  id: string;
  order_number: string;
  created_at: string;
  items: Array<GuestItemDTO>;
}

export interface CashierOrderDTO {
  id: string;
  order_number: string;
  created_at: string;
  items: Array<CashierItemDTO>;
}

export interface KitchenTicketDTO {
  id: string;
  order_number: string;
  created_at: string;
  table: TableRefDTO;
  bill_id: string;
  items: Array<KitchenItemDTO>;
}

export interface BillSummaryDTO {
  id: string;
  table_number: number;
  status: BillStatus;
  version: number;
  total_vnd: MoneyVndString;
  can_pay: boolean;
}

export interface PaidBillSummaryDTO {
  id: string;
  status: "paid";
  version: number;
  total_vnd: MoneyVndString;
}

export interface PaymentDTO {
  id: string;
  bill_id: string;
  shift_id: string;
  amount_vnd: MoneyVndString;
  method: PaymentMethod;
  paid_at: string;
}

export interface GuestBillDTO {
  id: string;
  table_id: string;
  table_number: number;
  status: BillStatus;
  version: number;
  opened_at: string;
  paid_at: string | null;
  total_vnd: MoneyVndString;
  can_pay: boolean;
  orders: Array<GuestOrderDTO>;
  payment: PaymentDTO | unknown;
  event_cursor: CursorString;
}

export interface CashierBillDTO {
  id: string;
  table_id: string;
  table_number: number;
  status: BillStatus;
  version: number;
  opened_at: string;
  paid_at: string | null;
  total_vnd: MoneyVndString;
  can_pay: boolean;
  orders: Array<CashierOrderDTO>;
  payment: PaymentDTO | unknown;
  event_cursor: CursorString;
}

export interface CashierTableDTO {
  id: string;
  number: number;
  label: string;
  status: TableDerivedStatus;
  bill_id: string | null;
  total_vnd: MoneyVndString;
  version: number | null;
  can_pay: boolean;
}

export interface ShiftDTO {
  id: string;
  status: ShiftStatus;
  opened_at: string;
  closed_at: string | null;
  version: number;
}

export interface RecommendationEntryDTO {
  item: GuestMenuItemDTO;
  reason: RecommendationReason;
}

export interface ReportTopItemDTO {
  menu_item_id: string;
  name: string;
  quantity: number;
}

export interface SseBusinessEventData {
  id: CursorString;
  type: "order.created" | "item.updated" | "bill.updated" | "bill.closed" | "menu.updated" | "shift.updated";
  resource_id: string;
  version: number;
  occurred_at: string;
}

export interface SseCheckpointEventData {
  cursor: CursorString;
}

export interface SseControlEventData {
  reason: string;
}

export interface HealthLiveResponse {
  data: {
    status: "ok";
  };
}

export interface HealthReadyResponse {
  data: {
    status: "ready";
    schema_revision: string;
  };
}

export interface AuthBootstrapResponse {
  data: {
    csrf_token: string;
    expires_at: string;
  };
}

export interface StaffSessionResponse {
  data: {
    staff: StaffDTO;
    csrf_token: string;
    expires_at: string;
  };
}

export interface GuestBootstrapResponse {
  data: {
    guest_id: string;
    csrf_token: string;
    expires_at: string;
    table: TableRefDTO;
    current_bill_id: string | null;
  };
}

export interface GuestJoinResponse {
  data: {
    bill_id: string | null;
    membership: boolean;
  };
}

export interface GuestMenuResponse {
  data: {
    categories: Array<CategoryDTO>;
    items: Array<GuestMenuItemDTO>;
    version: CursorString;
    event_cursor: CursorString;
    shift_open: boolean;
  };
}

export interface OrderSubmitResponse {
  data: {
    order: GuestOrderDTO;
    bill: BillSummaryDTO;
    event_cursor: CursorString;
  };
}

export interface GuestBillResponse {
  data: GuestBillDTO;
}

export interface ItemCancelResponse {
  data: {
    item: GuestItemDTO;
    bill: BillSummaryDTO;
    event_cursor: CursorString;
  };
}

export interface KitchenQueueResponse {
  data: Array<KitchenTicketDTO>;
  meta: PaginationMeta;
  event_cursor: CursorString;
  shift_open: boolean;
}

export interface KitchenItemMutationResponse {
  data: {
    item: KitchenItemDTO;
    event_cursor: CursorString;
  };
}

export interface KitchenMenuResponse {
  data: {
    items: Array<KitchenMenuItemDTO>;
    event_cursor: CursorString;
    shift_open: boolean;
  };
}

export interface KitchenAvailabilityMutationResponse {
  data: {
    item: KitchenMenuItemDTO;
    event_cursor: CursorString;
  };
}

export interface CashierTablesResponse {
  data: Array<CashierTableDTO>;
  meta: PaginationMeta;
  event_cursor: CursorString;
}

export interface CashierBillResponse {
  data: CashierBillDTO;
}

export interface PaymentReceiptResponse {
  data: {
    payment: PaymentDTO;
    bill: PaidBillSummaryDTO;
    table: {
      number: number;
      status: "free";
    };
    event_cursor: CursorString;
  };
}

export interface CurrentShiftResponse {
  data: {
    shift: ShiftDTO | unknown;
    event_cursor: CursorString;
  };
}

export interface ShiftMutationResponse {
  data: {
    shift: ShiftDTO;
    event_cursor: CursorString;
  };
}

export interface TableQrExportResponse {
  data: {
    table_number: number;
    url: string;
  };
}

export interface GuestRecommendationsResponse {
  data: {
    items: Array<RecommendationEntryDTO>;
    event_cursor: CursorString;
  };
}

export interface ShiftReportResponse {
  data: {
    shift: ShiftDTO;
    revenue_vnd: MoneyVndString;
    paid_bill_count: number;
    top_items: Array<ReportTopItemDTO>;
    as_of: string;
    event_cursor: CursorString;
  };
}
