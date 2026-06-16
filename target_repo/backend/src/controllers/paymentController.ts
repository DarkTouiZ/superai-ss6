/** PaySwift HTTP handlers: capture a payment, issue a refund, read payments. */
import { Request, Response, NextFunction } from 'express';
import { z } from 'zod';
import * as paymentService from '../services/paymentService';
import * as paymentRepo from '../repositories/paymentRepository';

export const refundSchema = z.object({
  order_id: z.number().int().positive(),
  payment_id: z.number().int().positive(),
  amount_satang: z.number().int().positive(),
  reason: z.string().min(1),
});

export async function capturePayment(req: Request, res: Response, next: NextFunction): Promise<void> {
  try {
    await paymentService.capture(Number(req.params.id));
    res.json({ ok: true });
  } catch (err) {
    next(err);
  }
}

export async function refundPayment(req: Request, res: Response, next: NextFunction): Promise<void> {
  try {
    const b = req.body as z.infer<typeof refundSchema>;
    const refundId = await paymentService.refund(b.order_id, b.payment_id, b.amount_satang, b.reason);
    res.status(201).json({ refundId });
  } catch (err) {
    next(err);
  }
}

export async function getPaymentsForOrder(req: Request, res: Response, next: NextFunction): Promise<void> {
  try {
    res.json({ payments: await paymentRepo.findByOrder(Number(req.params.orderId)) });
  } catch (err) {
    next(err);
  }
}
