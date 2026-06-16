/** Product/catalog HTTP handlers — thin: parse, delegate to repository, respond. */
import { Request, Response, NextFunction } from 'express';
import * as products from '../repositories/productRepository';

export async function getProducts(req: Request, res: Response, next: NextFunction): Promise<void> {
  try {
    const categoryId = req.query.categoryId ? Number(req.query.categoryId) : undefined;
    res.json({ products: await products.listProducts(categoryId) });
  } catch (err) {
    next(err);
  }
}

export async function getLowStock(_req: Request, res: Response, next: NextFunction): Promise<void> {
  try {
    res.json({ products: await products.lowStockProducts() });
  } catch (err) {
    next(err);
  }
}
