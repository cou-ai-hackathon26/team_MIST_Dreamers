// Bangladeshi mobile numbers (FR-APP-01). Same rule as the backend's PhoneNumber.parse:
// 01XXXXXXXXX, 8801XXXXXXXXX or +8801XXXXXXXXX, spaces, dashes and brackets allowed,
// result in E.164 (+8801[3-9]XXXXXXXX). Bangla digits (০-৯) are accepted too.

const E164_BD_MOBILE = /^\+8801[3-9]\d{8}$/

const BANGLA_ZERO = '০'.charCodeAt(0)

/** Turns Bangla digits into ASCII digits: "০১৭" -> "017". */
export function toAsciiDigits(text: string): string {
  return text.replace(/[০-৯]/g, (d) => String(d.charCodeAt(0) - BANGLA_ZERO))
}

/** Returns the number in E.164 form, or null if it is not a Bangladeshi mobile number. */
export function normalizePhone(raw: string): string | null {
  const cleaned = toAsciiDigits(raw ?? '').replace(/[\s\-()]/g, '')
  let candidate: string
  if (cleaned.startsWith('+')) candidate = cleaned
  else if (cleaned.startsWith('880')) candidate = '+' + cleaned
  else if (cleaned.startsWith('0')) candidate = '+88' + cleaned
  else return null
  return E164_BD_MOBILE.test(candidate) ? candidate : null
}

/** "+8801712345678" -> "01712345678" (how people write it). */
export function localPhone(e164: string): string {
  return e164.startsWith('+88') ? e164.slice(3) : e164
}
