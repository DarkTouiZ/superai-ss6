/** Order HTTP handlers — validate input, delegate to orderService, respond. */
import { Request, Response, NextFunction } from 'express';
import { z } from 'zod';
import * as orderService from '../services/orderService';

export const newOrderSchema = z.object({
  customer_id: z.number().int().positive(),
  address_id: z.number().int().positive(),
  store_id: z.number().int().positive(),
  fulfillment_type: z.enum(['delivery', 'pickup']).default('delivery'),
  discount_satang: z.number().int().nonnegative().optional(),
  lines: z
    .array(
      z.object({
        product_id: z.number().int().positive(),
        qty: z.number().int().positive(),
      }),
    )
    .min(1),
});

export async function createOrder(req: Request, res: Response, next: NextFunction): Promise<void> {
  try {
    const body = req.body as z.infer<typeof newOrderSchema>;
    const result = await orderService.placeOrder(
      {
        customer_id: body.customer_id,
        address_id: body.address_id,
        lines: body.lines,
        discount_satang: body.discount_satang,
      },
      { storeId: body.store_id, fulfillment: body.fulfillment_type },
    );
    res.status(201).json(result);
  } catch (err) {
    next(err);
  }
}

export async function getOrder(req: Request, res: Response, next: NextFunction): Promise<void> {
  try {
    const order = await orderService.getOrder(Number(req.params.id));
    if (!order) {
      res.status(404).json({ error: 'not_found' });
      return;
    }
    res.json(order);
  } catch (err) {
    next(err);
  }
}

export async function listOrders(req: Request, res: Response, next: NextFunction): Promise<void> {
  try {
    const status = req.query.status as undefined | string;
    res.json({ orders: await orderService.listOrders(status as never) });
  } catch (err) {
    next(err);
  }
}
