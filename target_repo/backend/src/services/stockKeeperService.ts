/**
 * StockKeeper — per-store inventory, branch-to-branch transfers, and low-stock
 * alerts (fanned out on SNS). Pure threshold/transfer logic is unit-tested.
 */
import { serviceName } from './registry';
import * as inv from '../repositories/storeInventoryRepository';
import { publishOrderEvent } from '../aws/snsClient';
import { logger } from '../utils/logger';

export const SERVICE = serviceName('inventory'); // "StockKeeper"

/** Pure: is this line at/under its reorder threshold? */
export function needsRestock(qtyOnHand: number, reorderLevel: number): boolean {
  return qtyOnHand <= reorderLevel;
}

/** Pure: can `qty` be moved out of a store that holds `available`? */
export function canTransfer(available: number, qty: number): boolean {
  return Number.isInteger(qty) && qty > 0 && qty <= available;
}

/** Move stock between branches if the source has enough on hand. */
export async function transferStock(
  fromStoreId: number,
  toStoreId: number,
  productId: number,
  qty: number,
): Promise<number> {
  if (fromStoreId === toStoreId) throw new Error('cannot transfer to the same store');
  const available = await inv.getQty(fromStoreId, productId);
  if (!canTransfer(available, qty)) throw new Error(`insufficient stock to transfer (have ${available})`);
  await inv.adjustQty(fromStoreId, productId, -qty);
  await inv.adjustQty(toStoreId, productId, qty);
  const id = await inv.recordTransfer(fromStoreId, toStoreId, productId, qty);
  logger.info('stock transferred', { service: SERVICE, fromStoreId, toStoreId, productId, qty });
  return id;
}

/** Find low-stock lines for a store and publish an alert if any. */
export async function checkLowStock(storeId: number): Promise<Array<{ product_id: number; qty_on_hand: number; reorder_level: number }>> {
  const low = await inv.lowStock(storeId);
  if (low.length > 0) {
    await publishOrderEvent(
      { service: SERVICE, event: 'low_stock', storeId, count: low.length, products: low.map((l) => l.product_id) },
      { event: 'low_stock' },
    );
    logger.warn('low stock alert', { service: SERVICE, storeId, count: low.length });
  }
  return low;
}
