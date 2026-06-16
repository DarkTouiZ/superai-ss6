import { couponDiscount, pointsRedemptionDiscount, Promotion, POINT_VALUE_SATANG } from '../promotionService';
import { refundableAmount, canTransition, Payment } from '../paymentService';
import { needsRestock, canTransfer } from '../stockKeeperService';
import { serviceName, serviceCatalog } from '../registry';

const promo = (over: Partial<Promotion>): Promotion => ({
  id: 1, code: 'X', kind: 'percent', value: 10, min_subtotal_satang: 0,
  max_discount_satang: null, is_active: true, ...over,
});

describe('PerksEngine — couponDiscount', () => {
  it('applies a percent discount capped at max_discount', () => {
    const r = couponDiscount(promo({ kind: 'percent', value: 15, max_discount_satang: 8000 }), 100000, 2900);
    expect(r.applicable).toBe(true);
    expect(r.discount_satang).toBe(8000); // 15% of 100000 = 15000, capped at 8000
  });
  it('applies a fixed discount, never exceeding subtotal', () => {
    expect(couponDiscount(promo({ kind: 'fixed', value: 5000 }), 20000, 2900).discount_satang).toBe(5000);
    expect(couponDiscount(promo({ kind: 'fixed', value: 50000 }), 20000, 2900).discount_satang).toBe(20000);
  });
  it('free_delivery returns the delivery fee as the discount', () => {
    const r = couponDiscount(promo({ kind: 'free_delivery' }), 20000, 2900);
    expect(r.free_delivery).toBe(true);
    expect(r.discount_satang).toBe(2900);
  });
  it('rejects below the minimum subtotal', () => {
    expect(couponDiscount(promo({ min_subtotal_satang: 30000 }), 20000, 2900).applicable).toBe(false);
  });
  it('rejects inactive promotions', () => {
    expect(couponDiscount(promo({ is_active: false }), 50000, 0).applicable).toBe(false);
  });
});

describe('PerksEngine — points redemption', () => {
  it('values points at the configured rate and caps at the order total', () => {
    expect(pointsRedemptionDiscount(100, 100000)).toBe(100 * POINT_VALUE_SATANG);
    expect(pointsRedemptionDiscount(100000, 5000)).toBe(5000); // capped at total
    expect(pointsRedemptionDiscount(-5, 5000)).toBe(0);
  });
});

describe('PaySwift — refunds & transitions', () => {
  const captured: Payment = { id: 1, order_id: 1, status: 'captured', amount_satang: 24600 };
  it('refundable only when captured, net of prior refunds', () => {
    expect(refundableAmount(captured, 0)).toBe(24600);
    expect(refundableAmount(captured, 4600)).toBe(20000);
    expect(refundableAmount({ ...captured, status: 'authorized' }, 0)).toBe(0);
  });
  it('enforces the lifecycle state machine', () => {
    expect(canTransition('pending', 'authorized')).toBe(true);
    expect(canTransition('authorized', 'captured')).toBe(true);
    expect(canTransition('captured', 'refunded')).toBe(true);
    expect(canTransition('refunded', 'captured')).toBe(false);
    expect(canTransition('pending', 'captured')).toBe(false);
  });
});

describe('StockKeeper — thresholds & transfers', () => {
  it('flags restock at or below the reorder level', () => {
    expect(needsRestock(10, 10)).toBe(true);
    expect(needsRestock(11, 10)).toBe(false);
  });
  it('only allows a valid positive transfer within available stock', () => {
    expect(canTransfer(20, 5)).toBe(true);
    expect(canTransfer(5, 20)).toBe(false);
    expect(canTransfer(20, 0)).toBe(false);
    expect(canTransfer(20, 2.5)).toBe(false);
  });
});

describe('service registry — branded codenames', () => {
  it('maps keys to product codenames', () => {
    expect(serviceName('payments')).toBe('PaySwift');
    expect(serviceName('inventory')).toBe('StockKeeper');
    expect(serviceName('unknown')).toBe('unknown');
  });
  it('exposes a full catalog', () => {
    expect(serviceCatalog().length).toBeGreaterThanOrEqual(9);
  });
});
