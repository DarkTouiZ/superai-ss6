/**
 * Order service — orchestrates placing an order end to end:
 *   price -> persist (txn) -> decrement stock -> create delivery row
 *   -> enqueue SQS order-processing -> publish SNS lifecycle -> award ALL points.
 * Controllers call this; they contain no business logic themselves (context.md §4).
 */
import { config } from '../config';
import { NewOrderInput, Order } from '../types/models';
import { priceOrder, pointsEarned } from './pricing';
import * as products from '../repositories/productRepository';
import * as orders from '../repositories/orderRepository';
import * as customers from '../repositories/customerRepository';
import * as deliveries from '../repositories/deliveryRepository';
import { enqueue } from '../aws/sqsClient';
import { publishLifecycleEvent } from './notificationService';
import { logger } from '../utils/logger';
import { serviceName } from './registry';
import { ValidationError } from './errors';

/** Branded codename for this service (see registry.ts). */
const SERVICE = serviceName('orders'); // "OrderForge"

// Re-exported for backward compatibility (callers import it from here).
export { ValidationError };

function makeOrderNo(seq: number): string {
  const d = new Date();
  const ymd = `${d.getFullYear().toString().slice(2)}${String(d.getMonth() + 1).padStart(2, '0')}${String(
    d.getDate(),
  ).padStart(2, '0')}`;
  return `E7-${ymd}-${String(seq % 10000).padStart(4, '0')}`;
}

export interface PlaceOrderResult {
  orderId: number;
  orderNo: string;
  totalSatang: number;
  pointsEarned: number;
}

export async function placeOrder(
  input: NewOrderInput,
  ctx: { storeId: number; fulfillment: 'delivery' | 'pickup' },
): Promise<PlaceOrderResult> {
  if (!input.lines?.length) throw new ValidationError('order must contain at least one line');

  const customer = await customers.findCustomerById(input.customer_id);
  if (!customer) throw new ValidationError(`unknown customer ${input.customer_id}`);
  const address = await customers.findAddressById(input.address_id);
  if (!address || address.customer_id !== input.customer_id) {
    throw new ValidationError('address does not belong to customer');
  }

  // Price against the live catalog.
  const catalog = await products.findProductsByIds(input.lines.map((l) => l.product_id));
  const breakdown = priceOrder(input.lines, catalog, {
    fulfillment: ctx.fulfillment,
    discount_satang: input.discount_satang,
  });

  // Stock check (best-effort; real system would lock rows).
  for (const line of breakdown.lines) {
    const onHand = await products.getStockOnHand(line.product_id);
    if (onHand < line.qty) {
      throw new ValidationError(`insufficient stock for "${line.product_name}" (have ${onHand}, need ${line.qty})`);
    }
  }

  const orderNo = makeOrderNo(Date.now());
  const orderId = await orders.createOrder({
    order_no: orderNo,
    customer_id: input.customer_id,
    address_id: input.address_id,
    store_id: ctx.storeId,
    fulfillment_type: ctx.fulfillment,
    subtotal_satang: breakdown.subtotal_satang,
    delivery_fee_satang: breakdown.delivery_fee_satang,
    discount_satang: breakdown.discount_satang,
    total_satang: breakdown.total_satang,
    items: breakdown.lines,
  });

  for (const line of breakdown.lines) {
    await products.decrementStock(line.product_id, line.qty);
  }

  await deliveries.createDelivery(orderId);

  // Async fulfillment: hand the order to the processing queue + announce on SNS.
  await enqueue(config.aws.sqsOrderQueueUrl, { orderId, orderNo, zone: address.district });
  await publishLifecycleEvent(orderId, 'order_placed', { orderNo });

  const earned = pointsEarned(breakdown.subtotal_satang);
  await customers.addPoints(input.customer_id, earned);

  logger.info('order placed', { service: SERVICE, orderId, orderNo, total: breakdown.total_satang });
  return { orderId, orderNo, totalSatang: breakdown.total_satang, pointsEarned: earned };
}

export async function getOrder(id: number): Promise<Order | null> {
  return orders.findOrderById(id);
}

export async function listOrders(status?: Order['status']): Promise<Order[]> {
  return orders.listOrders(status);
}
