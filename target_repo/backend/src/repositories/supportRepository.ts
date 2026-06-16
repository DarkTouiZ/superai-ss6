/** CareDesk data access: support tickets, messages, and returns. */
import { RowDataPacket, ResultSetHeader } from 'mysql2/promise';
import { query, execute } from '../db/pool';
import { NewTicket, TicketStatus } from '../services/careDeskService';

export async function createTicket(t: NewTicket): Promise<number> {
  const res: ResultSetHeader = await execute(
    `INSERT INTO support_tickets (order_id, customer_id, subject, category, priority, status)
     VALUES (:orderId, :customerId, :subject, :category, :priority, 'open')`,
    {
      orderId: t.orderId,
      customerId: t.customerId,
      subject: t.subject,
      category: t.category,
      priority: t.priority ?? 'normal',
    },
  );
  return res.insertId;
}

export async function addMessage(ticketId: number, author: 'customer' | 'agent', body: string): Promise<void> {
  await execute(
    `INSERT INTO ticket_messages (ticket_id, author, body) VALUES (:ticketId, :author, :body)`,
    { ticketId, author, body },
  );
}

export async function setTicketStatus(ticketId: number, status: TicketStatus): Promise<void> {
  await execute(`UPDATE support_tickets SET status = :status WHERE id = :ticketId`, { status, ticketId });
}

export async function listTickets(status?: TicketStatus): Promise<RowDataPacket[]> {
  if (status) {
    return query<RowDataPacket[]>(
      `SELECT id, order_id, customer_id, subject, category, priority, status, created_at
         FROM support_tickets WHERE status = :status ORDER BY created_at DESC`,
      { status },
    );
  }
  return query<RowDataPacket[]>(
    `SELECT id, order_id, customer_id, subject, category, priority, status, created_at
       FROM support_tickets ORDER BY created_at DESC`,
  );
}

export async function createReturn(orderId: number, reason: string): Promise<number> {
  const res: ResultSetHeader = await execute(
    `INSERT INTO returns (order_id, reason, status) VALUES (:orderId, :reason, 'requested')`,
    { orderId, reason },
  );
  return res.insertId;
}
