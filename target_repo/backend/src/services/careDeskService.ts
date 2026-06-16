/**
 * CareDesk — returns + support tickets. Business logic for opening tickets,
 * appending messages, resolving, and raising/approving returns.
 */
import { serviceName } from './registry';
import * as support from '../repositories/supportRepository';
import { logger } from '../utils/logger';

export const SERVICE = serviceName('support'); // "CareDesk"

export type TicketStatus = 'open' | 'pending' | 'resolved' | 'closed';
export type ReturnStatus = 'requested' | 'approved' | 'picked_up' | 'refunded' | 'rejected';

/** Pure: legal ticket status transitions. */
export function canCloseTicket(status: TicketStatus): boolean {
  return status === 'resolved';
}

export interface NewTicket {
  customerId: number;
  orderId: number | null;
  subject: string;
  category: 'delivery' | 'payment' | 'product' | 'account' | 'other';
  priority?: 'low' | 'normal' | 'high' | 'urgent';
}

export async function openTicket(t: NewTicket): Promise<number> {
  const id = await support.createTicket(t);
  logger.info('ticket opened', { service: SERVICE, ticketId: id, category: t.category });
  return id;
}

export async function addMessage(ticketId: number, author: 'customer' | 'agent', body: string): Promise<void> {
  await support.addMessage(ticketId, author, body);
}

export async function resolveTicket(ticketId: number): Promise<void> {
  await support.setTicketStatus(ticketId, 'resolved');
  logger.info('ticket resolved', { service: SERVICE, ticketId });
}

export async function requestReturn(orderId: number, reason: string): Promise<number> {
  const id = await support.createReturn(orderId, reason);
  logger.info('return requested', { service: SERVICE, orderId, returnId: id });
  return id;
}
