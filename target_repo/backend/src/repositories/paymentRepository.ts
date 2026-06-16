/** PaySwift data access: payments, payment_events, refunds. */
import { RowDataPacket, ResultSetHeader } from 'mysql2/promise';
import { query, execute } from '../db/pool';
import { Payment, PaymentStatus } from '../services/paymentService';

type PaymentRow = Payment & RowDataPacket & { provider_ref: string | null };

export async function findById(id: number): Promise<(Payment & { provider_ref: string | null }) | null> {
  const rows = await query<PaymentRow[]>(
    `SELECT id, order_id, status, amount_satang, provider_ref FROM payments WHERE id = :id`,
    { id },
  );
  return rows[0] ?? null;
}

export async function findByOrder(orderId: number): Promise<Payment[]> {
  return query<PaymentRow[]>(
    `SELECT id, order_id, status, amount_satang FROM payments WHERE order_id = :orderId`,
    { orderId },
  );
}

export async function setStatus(id: number, status: PaymentStatus): Promise<void> {
  await execute(`UPDATE payments SET status = :status WHERE id = :id`, { status, id });
}

export async function recordEvent(
  paymentId: number,
  type: 'authorized' | 'captured' | 'refunded' | 'failed' | 'voided',
  amountSatang: number,
  providerRef: string | null,
): Promise<void> {
  await execute(
    `INSERT INTO payment_events (payment_id, type, amount_satang, provider_ref)
     VALUES (:paymentId, :type, :amountSatang, :providerRef)`,
    { paymentId, type, amountSatang, providerRef },
  );
}

export async function totalRefunded(paymentId: number): Promise<number> {
  const rows = await query<RowDataPacket[]>(
    `SELECT COALESCE(SUM(amount_satang),0) AS refunded
       FROM payment_events WHERE payment_id = :paymentId AND type = 'refunded'`,
    { paymentId },
  );
  return Number(rows[0]?.refunded ?? 0);
}

export async function createRefund(
  orderId: number,
  paymentId: number,
  amountSatang: number,
  reason: string,
): Promise<number> {
  const res: ResultSetHeader = await execute(
    `INSERT INTO refunds (order_id, payment_id, amount_satang, reason, status)
     VALUES (:orderId, :paymentId, :amountSatang, :reason, 'processed')`,
    { orderId, paymentId, amountSatang, reason },
  );
  return res.insertId;
}
