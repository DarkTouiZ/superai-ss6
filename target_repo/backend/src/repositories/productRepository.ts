/**
 * Product/inventory data access. All product reads go through here — controllers
 * and services never write SQL directly (context.md §4).
 */
import { RowDataPacket } from 'mysql2/promise';
import { query, execute } from '../db/pool';
import { Product } from '../types/models';

type ProductRow = Product & RowDataPacket;

export async function listProducts(categoryId?: number): Promise<Product[]> {
  if (categoryId) {
    return query<ProductRow[]>(
      `SELECT id, category_id, sku, name, description, unit, price_satang, is_active
         FROM products
        WHERE is_active = 1 AND category_id = :categoryId
        ORDER BY name`,
      { categoryId },
    );
  }
  return query<ProductRow[]>(
    `SELECT id, category_id, sku, name, description, unit, price_satang, is_active
       FROM products WHERE is_active = 1 ORDER BY category_id, name`,
  );
}

export async function findProductById(id: number): Promise<Product | null> {
  const rows = await query<ProductRow[]>(
    `SELECT id, category_id, sku, name, description, unit, price_satang, is_active
       FROM products WHERE id = :id`,
    { id },
  );
  return rows[0] ?? null;
}

export async function findProductsByIds(ids: number[]): Promise<Product[]> {
  if (ids.length === 0) return [];
  const placeholders = ids.map(() => '?').join(',');
  return query<ProductRow[]>(
    `SELECT id, category_id, sku, name, description, unit, price_satang, is_active
       FROM products WHERE id IN (${placeholders})`,
    ids,
  );
}

export async function getStockOnHand(productId: number): Promise<number> {
  const rows = await query<RowDataPacket[]>(
    `SELECT qty_on_hand FROM inventory WHERE product_id = :productId`,
    { productId },
  );
  return rows[0]?.qty_on_hand ?? 0;
}

/** Decrement stock for a product; used when an order is confirmed. */
export async function decrementStock(productId: number, qty: number): Promise<void> {
  await execute(
    `UPDATE inventory SET qty_on_hand = GREATEST(qty_on_hand - :qty, 0)
       WHERE product_id = :productId`,
    { qty, productId },
  );
}

export async function lowStockProducts(): Promise<Array<Product & { qty_on_hand: number }>> {
  return query<(Product & { qty_on_hand: number } & RowDataPacket)[]>(
    `SELECT p.id, p.category_id, p.sku, p.name, p.description, p.unit, p.price_satang,
            p.is_active, i.qty_on_hand
       FROM products p JOIN inventory i ON i.product_id = p.id
      WHERE i.qty_on_hand <= i.reorder_level
      ORDER BY i.qty_on_hand ASC`,
  );
}
