/**
 * PerksEngine — coupons + ALL Member points (context.md §4: business logic in
 * services; money is integer satang). The discount math is pure and unit-tested;
 * persistence is delegated to repositories.
 */
import { serviceName } from './registry';
import * as promos from '../repositories/promotionRepository';
import * as customers from '../repositories/customerRepository';

export const SERVICE = serviceName('promotions'); // "PerksEngine"

/** 1 ALL Member point is worth 25 satang (THB 0.25) when redeemed. */
export const POINT_VALUE_SATANG = 25;

export interface Promotion {
  id: number;
  code: string;
  kind: 'percent' | 'fixed' | 'free_delivery';
  value: number;
  min_subtotal_satang: number;
  max_discount_satang: number | null;
  is_active: boolean;
}

export interface CouponResult {
  applicable: boolean;
  discount_satang: number;
  free_delivery: boolean;
  reason?: string;
}

/** Pure: compute the discount a coupon yields for a given subtotal + delivery fee. */
export function couponDiscount(
  promo: Promotion,
  subtotalSatang: number,
  deliveryFeeSatang: number,
): CouponResult {
  if (!promo.is_active) return { applicable: false, discount_satang: 0, free_delivery: false, reason: 'inactive' };
  if (subtotalSatang < promo.min_subtotal_satang) {
    return { applicable: false, discount_satang: 0, free_delivery: false, reason: 'below minimum subtotal' };
  }
  if (promo.kind === 'free_delivery') {
    return { applicable: true, discount_satang: deliveryFeeSatang, free_delivery: true };
  }
  if (promo.kind === 'fixed') {
    const d = Math.min(promo.value, subtotalSatang);
    return { applicable: true, discount_satang: d, free_delivery: false };
  }
  // percent
  let d = Math.floor((subtotalSatang * promo.value) / 100);
  if (promo.max_discount_satang != null) d = Math.min(d, promo.max_discount_satang);
  return { applicable: true, discount_satang: d, free_delivery: false };
}

/** Pure: satang value of redeeming N points (cannot exceed the order total). */
export function pointsRedemptionDiscount(points: number, totalSatang: number): number {
  const raw = Math.max(0, Math.trunc(points)) * POINT_VALUE_SATANG;
  return Math.min(raw, totalSatang);
}

/** Look up a coupon by code and evaluate it against a cart. */
export async function applyCoupon(
  code: string,
  subtotalSatang: number,
  deliveryFeeSatang: number,
): Promise<CouponResult> {
  const promo = await promos.findActiveByCode(code);
  if (!promo) return { applicable: false, discount_satang: 0, free_delivery: false, reason: 'unknown code' };
  return couponDiscount(promo, subtotalSatang, deliveryFeeSatang);
}

/** Redeem points for a customer: writes a ledger row and decrements the balance. */
export async function redeemPoints(
  customerId: number,
  points: number,
  orderId: number | null,
): Promise<number> {
  await promos.recordPointTransaction({ customerId, orderId, kind: 'redeem', points: -Math.abs(points), note: 'redeemed at checkout' });
  await customers.addPoints(customerId, -Math.abs(points));
  return Math.abs(points);
}
