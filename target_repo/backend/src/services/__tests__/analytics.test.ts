import { rankCustomersBySpend, TopCustomerRow } from '../analytics';

const rows: TopCustomerRow[] = [
  { customer_id: 1, full_name: 'A', loyalty_tier: 'gold', spend_satang: 5000 },
  { customer_id: 2, full_name: 'B', loyalty_tier: 'silver', spend_satang: 9000 },
  { customer_id: 3, full_name: 'C', loyalty_tier: 'standard', spend_satang: 1000 },
];

describe('rankCustomersBySpend (SS6-generated)', () => {
  it('sorts customers by spend descending', () => {
    expect(rankCustomersBySpend(rows).map((r) => r.customer_id)).toEqual([2, 1, 3]);
  });
  it('respects the limit', () => {
    expect(rankCustomersBySpend(rows, 2).length).toBe(2);
  });
});
