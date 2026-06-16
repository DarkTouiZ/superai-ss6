/** Dashboard HTTP handlers — revenue + operational summaries for the ops console. */
import { Request, Response, NextFunction } from 'express';
import { RowDataPacket } from 'mysql2/promise';
import { query } from '../db/pool';

export async function getRevenueSummary(_req: Request, res: Response, next: NextFunction): Promise<void> {
  try {
    const totals = await query<RowDataPacket[]>(
      `SELECT
          COUNT(*) AS orders,
          COALESCE(SUM(total_satang), 0) AS gross_satang,
          COALESCE(SUM(CASE WHEN status = 'delivered' THEN total_satang ELSE 0 END), 0) AS delivered_satang
        FROM orders
       WHERE status <> 'cancelled'`,
    );
    const byStatus = await query<RowDataPacket[]>(
      `SELECT status, COUNT(*) AS count FROM orders GROUP BY status`,
    );
    const topProducts = await query<RowDataPacket[]>(
      `SELECT product_name, SUM(qty) AS units, SUM(line_total_satang) AS revenue_satang
         FROM order_items
         GROUP BY product_name
         ORDER BY revenue_satang DESC
         LIMIT 5`,
    );
    res.json({ totals: totals[0], byStatus, topProducts });
  } catch (err) {
    next(err);
  }
}
