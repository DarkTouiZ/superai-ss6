/** Delivery/courier HTTP handlers. */
import { Request, Response, NextFunction } from 'express';
import * as couriers from '../repositories/courierRepository';
import * as deliveries from '../repositories/deliveryRepository';

export async function getCouriers(_req: Request, res: Response, next: NextFunction): Promise<void> {
  try {
    res.json({ couriers: await couriers.listCouriers() });
  } catch (err) {
    next(err);
  }
}

export async function getDeliveryForOrder(req: Request, res: Response, next: NextFunction): Promise<void> {
  try {
    const delivery = await deliveries.findDeliveryByOrder(Number(req.params.orderId));
    if (!delivery) {
      res.status(404).json({ error: 'not_found' });
      return;
    }
    res.json(delivery);
  } catch (err) {
    next(err);
  }
}
