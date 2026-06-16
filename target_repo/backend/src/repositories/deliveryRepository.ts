/** Delivery rows — one per order once it enters fulfillment. */
import { RowDataPacket, ResultSetHeader } from 'mysql2/promise';
import { query, execute } from '../db/pool';
import { Delivery, DeliveryStatus } from '../types/models';

type DeliveryRow = Delivery & RowDataPacket;

export async function createDelivery(orderId: number): Promise<number> {
  const res: ResultSetHeader = await execute(
    `INSERT INTO deliveries (order_id, status) VALUES (:orderId, 'queued')`,
    { orderId },
  );
  return res.insertId;
}

export async function assignCourier(
  deliveryId: number,
  courierId: number,
  etaMinutes: number,
): Promise<void> {
  await execute(
    `UPDATE deliveries
        SET courier_id = :courierId, status = 'assigned',
            eta_minutes = :etaMinutes, assigned_at = CURRENT_TIMESTAMP
      WHERE id = :deliveryId`,
    { courierId, etaMinutes, deliveryId },
  );
}

export async function setDeliveryStatus(
  deliveryId: number,
  status: DeliveryStatus,
): Promise<void> {
  const delivered = status === 'delivered' ? ', delivered_at = CURRENT_TIMESTAMP' : '';
  await execute(
    `UPDATE deliveries SET status = :status${delivered} WHERE id = :deliveryId`,
    { status, deliveryId },
  );
}

export async function findDeliveryByOrder(orderId: number): Promise<Delivery | null> {
  const rows = await query<DeliveryRow[]>(
    `SELECT id, order_id, courier_id, status, eta_minutes FROM deliveries WHERE order_id = :orderId`,
    { orderId },
  );
  return rows[0] ?? null;
}
