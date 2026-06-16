/**
 * Money helpers — eleven-7 stores ALL money as integer minor units (satang).
 * context.md §4: never use floats for money; format only at the edge (here / view).
 * 1 THB = 100 satang.
 */

/** Add a list of satang amounts. Integer-only, no float drift. */
export function sumSatang(amounts: number[]): number {
  return amounts.reduce((acc, n) => acc + Math.trunc(n), 0);
}

/** qty * unit price, both integers, result in satang. */
export function lineTotal(qty: number, unitPriceSatang: number): number {
  if (qty < 0 || unitPriceSatang < 0) throw new Error('money: negative input');
  return Math.trunc(qty) * Math.trunc(unitPriceSatang);
}

/** Format satang as a THB string for SMS bodies / receipts, e.g. 24600 -> "THB 246.00". */
export function formatTHB(satang: number): string {
  const sign = satang < 0 ? '-' : '';
  const abs = Math.abs(Math.trunc(satang));
  const baht = Math.floor(abs / 100);
  const sub = abs % 100;
  const grouped = baht.toLocaleString('en-US');
  return `${sign}THB ${grouped}.${sub.toString().padStart(2, '0')}`;
}

/** Parse a THB decimal string (e.g. "246.00") into integer satang. */
export function toSatang(baht: number): number {
  return Math.round(baht * 100);
}
