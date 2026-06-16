/**
 * Pricing — pure functions, no I/O (context.md §4: business logic lives in services).
 * All amounts are integer satang. Every exported function has an explicit return type.
 */
import { lineTotal, sumSatang } from '../utils/money';
import { Product } from '../types/models';

export interface PricedLine {
  product_id: number;
  product_name: string;
  qty: number;
  unit_price_satang: number;
  line_total_satang: number;
}

export interface PriceBreakdown {
  lines: PricedLine[];
  subtotal_satang: number;
  delivery_fee_satang: number;
  discount_satang: number;
  total_satang: number;
}

/** Free delivery over this subtotal; pickup is always free. */
export const FREE_DELIVERY_THRESHOLD_SATANG = 30000; // THB 300
export const BASE_DELIVERY_FEE_SATANG = 2900; // THB 29
export const SMALL_ORDER_FEE_SATANG = 3500; // THB 35 under THB 150
export const SMALL_ORDER_LIMIT_SATANG = 15000; // THB 150

/** Compute a delivery fee from the subtotal and fulfillment type. */
export function deliveryFee(
  subtotalSatang: number,
  fulfillment: 'delivery' | 'pickup',
): number {
  if (fulfillment === 'pickup') return 0;
  if (subtotalSatang >= FREE_DELIVERY_THRESHOLD_SATANG) return 0;
  if (subtotalSatang < SMALL_ORDER_LIMIT_SATANG) return SMALL_ORDER_FEE_SATANG;
  return BASE_DELIVERY_FEE_SATANG;
}

/** ALL Member earn rate: 1 point per 10 THB (1000 satang) of subtotal, floored. */
export function pointsEarned(subtotalSatang: number): number {
  return Math.floor(subtotalSatang / 1000);
}

/**
 * Build a full price breakdown from cart lines and the catalog. Throws if a
 * product is missing or quantity is invalid — callers validate at the edge.
 */
export function priceOrder(
  cart: Array<{ product_id: number; qty: number }>,
  catalog: Product[],
  opts: { fulfillment: 'delivery' | 'pickup'; discount_satang?: number },
): PriceBreakdown {
  const byId = new Map(catalog.map((p) => [p.id, p]));
  const lines: PricedLine[] = cart.map((c) => {
    const p = byId.get(c.product_id);
    if (!p) throw new Error(`unknown product_id ${c.product_id}`);
    if (!Number.isInteger(c.qty) || c.qty <= 0) throw new Error(`bad qty for product ${c.product_id}`);
    return {
      product_id: p.id,
      product_name: p.name,
      qty: c.qty,
      unit_price_satang: p.price_satang,
      line_total_satang: lineTotal(c.qty, p.price_satang),
    };
  });
  const subtotal = sumSatang(lines.map((l) => l.line_total_satang));
  const discount = Math.max(0, Math.trunc(opts.discount_satang ?? 0));
  const fee = deliveryFee(subtotal, opts.fulfillment);
  const total = Math.max(0, subtotal + fee - discount);
  return {
    lines,
    subtotal_satang: subtotal,
    delivery_fee_satang: fee,
    discount_satang: discount,
    total_satang: total,
  };
}
