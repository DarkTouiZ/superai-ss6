/** StockKeeper data access: per-store inventory + transfers. */
import { RowDataPacket, ResultSetHeader } from 'mysql2/promise';
import { query, execute } from '../db/pool';

export async function getQty(storeId: number, productId: number): Promise<number> {
  const rows = await query<RowDataPacket[]>(
    `SELECT qty_on_hand FROM store_inventory WHERE store_id = :storeId AND product_id = :productId`,
    { storeId, productId },
  );
  return rows[0]?.qty_on_hand ?? 0;
}

export async function adjustQty(storeId: number, productId: number, delta: number): Promise<void> {
  await execute(
    `INSERT INTO store_inventory (store_id, product_id, qty_on_hand)
     VALUES (:storeId, :productId, GREATEST(:delta, 0))
     ON DUPLICATE KEY UPDATE qty_on_hand = GREATEST(qty_on_hand + :delta, 0)`,
    { storeId, productId, delta },
  );
}

export async function lowStock(
  storeId: number,
): Promise<Array<{ product_id: number; qty_on_hand: number; reorder_level: number }>> {
  return query<(RowDataPacket & { product_id: number; qty_on_hand: number; reorder_level: number })[]>(
    `SELECT product_id, qty_on_hand, reorder_level
       FROM store_inventory
      WHERE store_id = :storeId AND qty_on_hand <= reorder_level
      ORDER BY qty_on_hand ASC`,
    { storeId },
  );
}

export async function recordTransfer(
  fromStoreId: number,
  toStoreId: number,
  productId: number,
  qty: number,
): Promise<number> {
  const res: ResultSetHeader = await execute(
    `INSERT INTO stock_transfers (from_store_id, to_store_id, product_id, qty, status)
     VALUES (:fromStoreId, :toStoreId, :productId, :qty, 'in_transit')`,
    { fromStoreId, toStoreId, productId, qty },
  );
  return res.insertId;
}
