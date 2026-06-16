/**
 * Order persistence. Creating an order writes the order + its items atomically
 * inside a single transaction (db/pool.withTransaction).
 */
import { RowDataPacket, ResultSetHeader } from 'mysql2/promise';
import { query, withTransaction } from '../db/pool';
import { Order, OrderItem, OrderStatus } from '../types/models';

type OrderRow = Order & RowDataPacket;
type ItemRow = OrderItem & RowDataPacket;

export interface PersistOrderInput {
  order_no: string;
  customer_id: number;
  address_id: number;
  store_id: number;
  fulfillment_type: 'delivery' | 'pickup';
  subtotal_satang: number;
  delivery_fee_satang: number;
  discount_satang: number;
  total_satang: number;
  items: OrderItem[];
}

export async function createOrder(input: PersistOrderInput): Promise<number> {
  return withTransaction(async (conn) => {
    const [res] = await conn.execute<ResultSetHeader>(
      `INSERT INTO orders
         (order_no, customer_id, address_id, store_id, fulfillment_type, status,
          subtotal_satang, delivery_fee_satang, discount_satang, total_satang)
       VALUES (:order_no, :customer_id, :address_id, :store_id, :fulfillment_type, 'pending',
          :subtotal_satang, :delivery_fee_satang, :discount_satang, :total_satang)`,
      {
        order_no: input.order_no,
        customer_id: input.customer_id,
        address_id: input.address_id,
        store_id: input.store_id,
        fulfillment_type: input.fulfillment_type,
        subtotal_satang: input.subtotal_satang,
        delivery_fee_satang: input.delivery_fee_satang,
        discount_satang: input.discount_satang,
        total_satang: input.total_satang,
      } as never,
    );
    const orderId = res.insertId;
    for (const it of input.items) {
      await conn.execute(
        `INSERT INTO order_items
           (order_id, product_id, product_name, qty, unit_price_satang, line_total_satang)
         VALUES (:order_id, :product_id, :product_name, :qty, :unit_price_satang, :line_total_satang)`,
        {
          order_id: orderId,
          product_id: it.product_id,
          product_name: it.product_name,
          qty: it.qty,
          unit_price_satang: it.unit_price_satang,
          line_total_satang: it.line_total_satang,
        } as never,
      );
    }
    return orderId;
  });
}

export async function findOrderById(id: number): Promise<Order | null> {
  const rows = await query<OrderRow[]>(`SELECT * FROM orders WHERE id = :id`, { id });
  const order = rows[0];
  if (!order) return null;
  order.items = await query<ItemRow[]>(
    `SELECT product_id, product_name, qty, unit_price_satang, line_total_satang
       FROM order_items WHERE order_id = :id`,
    { id },
  );
  return order;
}

export async function listOrders(status?: OrderStatus): Promise<Order[]> {
  if (status) {
    return query<OrderRow[]>(
      `SELECT * FROM orders WHERE status = :status ORDER BY placed_at DESC`,
      { status },
    );
  }
  return query<OrderRow[]>(`SELECT * FROM orders ORDER BY placed_at DESC`);
}

export async function updateOrderStatus(id: number, status: OrderStatus): Promise<void> {
  await query(`UPDATE orders SET status = :status WHERE id = :id`, { status, id });
}
