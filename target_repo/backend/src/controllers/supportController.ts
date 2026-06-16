/** CareDesk HTTP handlers: tickets + returns. */
import { Request, Response, NextFunction } from 'express';
import { z } from 'zod';
import * as careDesk from '../services/careDeskService';
import * as supportRepo from '../repositories/supportRepository';

export const newTicketSchema = z.object({
  customer_id: z.number().int().positive(),
  order_id: z.number().int().positive().nullable().optional(),
  subject: z.string().min(3),
  category: z.enum(['delivery', 'payment', 'product', 'account', 'other']).default('other'),
  priority: z.enum(['low', 'normal', 'high', 'urgent']).optional(),
});

export const newReturnSchema = z.object({
  order_id: z.number().int().positive(),
  reason: z.string().min(3),
});

export async function listTickets(req: Request, res: Response, next: NextFunction): Promise<void> {
  try {
    res.json({ tickets: await supportRepo.listTickets(req.query.status as never) });
  } catch (err) {
    next(err);
  }
}

export async function openTicket(req: Request, res: Response, next: NextFunction): Promise<void> {
  try {
    const b = req.body as z.infer<typeof newTicketSchema>;
    const id = await careDesk.openTicket({
      customerId: b.customer_id,
      orderId: b.order_id ?? null,
      subject: b.subject,
      category: b.category,
      priority: b.priority,
    });
    res.status(201).json({ ticketId: id });
  } catch (err) {
    next(err);
  }
}

export async function requestReturn(req: Request, res: Response, next: NextFunction): Promise<void> {
  try {
    const b = req.body as z.infer<typeof newReturnSchema>;
    const id = await careDesk.requestReturn(b.order_id, b.reason);
    res.status(201).json({ returnId: id });
  } catch (err) {
    next(err);
  }
}
