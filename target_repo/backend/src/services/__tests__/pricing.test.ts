import {
  priceOrder,
  deliveryFee,
  pointsEarned,
  FREE_DELIVERY_THRESHOLD_SATANG,
} from '../pricing';
import { Product } from '../../types/models';

const catalog: Product[] = [
  { id: 1, category_id: 1, sku: 'A', name: 'Pork & Basil Rice Bowl', description: null, unit: 'box', price_satang: 3500, is_active: true },
  { id: 5, category_id: 2, sku: 'B', name: 'All Café Iced Americano', description: null, unit: 'cup', price_satang: 5800, is_active: true },
  { id: 9, category_id: 3, sku: 'C', name: 'Sourdough Loaf', description: null, unit: 'each', price_satang: 8900, is_active: true },
];

describe('pricing.priceOrder', () => {
  it('computes subtotal/total with integer satang and no float drift', () => {
    const b = priceOrder(
      [
        { product_id: 1, qty: 2 }, // 7000
        { product_id: 5, qty: 1 }, // 5800
        { product_id: 9, qty: 1 }, // 8900
      ],
      catalog,
      { fulfillment: 'delivery' },
    );
    expect(b.subtotal_satang).toBe(21700);
    expect(Number.isInteger(b.subtotal_satang)).toBe(true);
    expect(b.delivery_fee_satang).toBe(2900); // 21700 < free threshold, >= small-order limit
    expect(b.total_satang).toBe(24600);
  });

  it('applies a discount and never goes below zero', () => {
    const b = priceOrder([{ product_id: 1, qty: 1 }], catalog, {
      fulfillment: 'pickup',
      discount_satang: 999999,
    });
    expect(b.total_satang).toBe(0);
  });

  it('throws on unknown product or bad quantity', () => {
    expect(() => priceOrder([{ product_id: 999, qty: 1 }], catalog, { fulfillment: 'pickup' })).toThrow();
    expect(() => priceOrder([{ product_id: 1, qty: 0 }], catalog, { fulfillment: 'pickup' })).toThrow();
  });
});

describe('pricing.deliveryFee', () => {
  it('is free for pickup', () => {
    expect(deliveryFee(5000, 'pickup')).toBe(0);
  });
  it('is free over the threshold', () => {
    expect(deliveryFee(FREE_DELIVERY_THRESHOLD_SATANG, 'delivery')).toBe(0);
  });
  it('charges the small-order fee under THB 150', () => {
    expect(deliveryFee(9400, 'delivery')).toBe(3500);
  });
  it('charges the base fee between THB 150 and the free threshold', () => {
    expect(deliveryFee(20000, 'delivery')).toBe(2900);
  });
});

describe('pricing.pointsEarned', () => {
  it('awards 1 ALL Member point per 10 THB of subtotal, floored', () => {
    expect(pointsEarned(21700)).toBe(21);
    expect(pointsEarned(999)).toBe(0);
  });
});
