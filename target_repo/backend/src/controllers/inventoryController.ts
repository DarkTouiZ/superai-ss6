/** StockKeeper HTTP handlers: per-store low stock + transfers. */
import { Request, Response, NextFunction } from 'express';
import { z } from 'zod';
import * as stockKeeper from '../services/stockKeeperService';

export const transferSchema = z.object({
  from_store_id: z.number().int().positive(),
  to_store_id: z.number().int().positive(),
  product_id: z.number().int().positive(),
  qty: z.number().int().positive(),
});

export async function getLowStock(req: Request, res: Response, next: NextFunction): Promise<void> {
  try {
    const low = await stockKeeper.checkLowStock(Number(req.params.storeId));
    res.json({ storeId: Number(req.params.storeId), lowStock: low });
  } catch (err) {
    next(err);
  }
}

export async function transferStock(req: Request, res: Response, next: NextFunction): Promise<void> {
  try {
    const b = req.body as z.infer<typeof transferSchema>;
    const id = await stockKeeper.transferStock(b.from_store_id, b.to_store_id, b.product_id, b.qty);
    res.status(201).json({ transferId: id });
  } catch (err) {
    next(err);
  }
}
