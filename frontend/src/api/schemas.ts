import { z } from 'zod'

/** Giới hạn theo plan §9.1: quantity 1..20 integer, note trim <= 250, tối đa 50 dòng. */
export const cartLineSchema = z.object({
  menu_item_id: z.string().min(1),
  quantity: z.number().int().min(1, 'Số lượng tối thiểu 1').max(20, 'Mỗi dòng tối đa 20'),
  note: z.string().trim().max(250, 'Ghi chú tối đa 250 ký tự'),
  expected_unit_price_vnd: z.number().int().nonnegative(),
})

export const cartSchema = z
  .array(cartLineSchema)
  .min(1, 'Giỏ đang trống')
  .max(50, 'Một lượt gửi tối đa 50 dòng')

/** Password không trim (plan §11.2). */
export const loginSchema = z.object({
  username: z.string().trim().min(1, 'Nhập tài khoản'),
  password: z.string().min(1, 'Nhập mật khẩu'),
})

export const noteSchema = z.string().trim().max(250, 'Ghi chú tối đa 250 ký tự')

/** Lấy message đầu tiên của ZodError để hiện một dòng lỗi cho người dùng. */
export function firstIssue(error: unknown): string | null {
  return error instanceof z.ZodError ? (error.issues[0]?.message ?? 'Dữ liệu không hợp lệ.') : null
}
