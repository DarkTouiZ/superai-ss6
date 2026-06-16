/** PerksEngine data access: promotions + the ALL Member point ledger. */
import { RowDataPacket, ResultSetHeader } from 'mysql2/promise';
import { query, execute } from '../db/pool';
import { Promotion } from '../services/promotionService';

type PromoRow = Promotion & RowDataPacket;

export async function findActiveByCode(code: string): Promise<Promotion | null> {
  const rows = await query<PromoRow[]>(
    `SELECT id, code, kind, value, min_subtotal_satang, max_discount_satang, is_active
       FROM promotions
      WHERE code = :code AND is_active = 1
        AND (starts_at IS NULL OR starts_at <= CURRENT_TIMESTAMP)
        AND (ends_at   IS NULL OR ends_at   >= CURRENT_TIMESTAMP)`,
    { code },
  );
  return rows[0] ?? null;
}

export async function listActive(): Promise<Promotion[]> {
  return query<PromoRow[]>(
    `SELECT id, code, kind, value, min_subtotal_satang, max_discount_satang, is_active
       FROM promotions WHERE is_active = 1 ORDER BY code`,
  );
}

export interface PointTx {
  customerId: number;
  orderId: number | null;
  kind: 'earn' | 'redeem' | 'adjust';
  points: number;
  note?: string;
}

export async function recordPointTransaction(tx: PointTx): Promise<number> {
  const res: ResultSetHeader = await execute(
    `INSERT INTO point_transactions (customer_id, order_id, kind, points, note)
     VALUES (:customerId, :orderId, :kind, :points, :note)`,
    { customerId: tx.customerId, orderId: tx.orderId, kind: tx.kind, points: tx.points, note: tx.note ?? null },
  );
  return res.insertId;
}

export async function pointHistory(customerId: number): Promise<RowDataPacket[]> {
  return query<RowDataPacket[]>(
    `SELECT id, order_id, kind, points, note, created_at
       FROM point_transactions WHERE customer_id = :customerId ORDER BY created_at DESC`,
    { customerId },
  );
}
