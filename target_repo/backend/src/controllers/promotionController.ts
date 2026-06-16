/** PerksEngine HTTP handlers: validate a coupon, list promotions, point history. */
import { Request, Response, NextFunction } from 'express';
import { z } from 'zod';
import * as promoService from '../services/promotionService';
import * as promoRepo from '../repositories/promotionRepository';

export const validateCouponSchema = z.object({
  code: z.string().min(1),
  subtotal_satang: z.number().int().nonnegative(),
  delivery_fee_satang: z.number().int().nonnegative().default(0),
});

export async function validateCoupon(req: Request, res: Response, next: NextFunction): Promise<void> {
  try {
    const b = req.body as z.infer<typeof validateCouponSchema>;
    const result = await promoService.applyCoupon(b.code, b.subtotal_satang, b.delivery_fee_satang);
    res.json(result);
  } catch (err) {
    next(err);
  }
}

export async function listPromotions(_req: Request, res: Response, next: NextFunction): Promise<void> {
  try {
    res.json({ promotions: await promoRepo.listActive() });
  } catch (err) {
    next(err);
  }
}

export async function pointHistory(req: Request, res: Response, next: NextFunction): Promise<void> {
  try {
    res.json({ history: await promoRepo.pointHistory(Number(req.params.customerId)) });
  } catch (err) {
    next(err);
  }
}
