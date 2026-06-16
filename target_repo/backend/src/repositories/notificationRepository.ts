/** Notification outbox — every SMS/SNS the app emits is recorded here. */
import { RowDataPacket, ResultSetHeader } from 'mysql2/promise';
import { query, execute } from '../db/pool';

export interface NotificationRecord {
  customer_id: number | null;
  order_id: number | null;
  channel: 'sms' | 'sns_topic' | 'email';
  template: string;
  destination: string;
  body: string;
  status: 'queued' | 'sent' | 'failed';
  provider_message_id: string | null;
}

export async function recordNotification(n: NotificationRecord): Promise<number> {
  const res: ResultSetHeader = await execute(
    `INSERT INTO notifications
       (customer_id, order_id, channel, template, destination, body, status, provider_message_id)
     VALUES (:customer_id, :order_id, :channel, :template, :destination, :body, :status, :provider_message_id)`,
    { ...n },
  );
  return res.insertId;
}

export async function listNotificationsForOrder(orderId: number): Promise<RowDataPacket[]> {
  return query<RowDataPacket[]>(
    `SELECT id, channel, template, destination, body, status, provider_message_id, created_at
       FROM notifications WHERE order_id = :orderId ORDER BY created_at`,
    { orderId },
  );
}
