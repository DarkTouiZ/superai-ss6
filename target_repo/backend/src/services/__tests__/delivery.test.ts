import { estimateEta } from '../deliveryService';
import { formatTHB, sumSatang, lineTotal } from '../../utils/money';

describe('deliveryService.estimateEta', () => {
  it('is faster by motorbike than by bicycle for the same distance', () => {
    expect(estimateEta(4, 'motorbike')).toBeLessThan(estimateEta(4, 'bicycle'));
  });
  it('never returns less than the 10-minute floor', () => {
    expect(estimateEta(0, 'car')).toBeGreaterThanOrEqual(10);
  });
  it('is deterministic', () => {
    expect(estimateEta(6, 'van')).toBe(estimateEta(6, 'van'));
  });
});

describe('money helpers', () => {
  it('formats satang as THB with two decimals and grouping', () => {
    expect(formatTHB(24600)).toBe('THB 246.00');
    expect(formatTHB(100000)).toBe('THB 1,000.00');
    expect(formatTHB(5)).toBe('THB 0.05');
  });
  it('sums and multiplies as pure integers', () => {
    expect(sumSatang([7000, 5800, 8900])).toBe(21700);
    expect(lineTotal(3, 2500)).toBe(7500);
  });
});
