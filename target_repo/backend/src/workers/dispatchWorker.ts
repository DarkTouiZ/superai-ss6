/**
 * Delivery-dispatch worker — consumes the SQS dispatch queue, assigns an available
 * courier in the order's zone, moves the order to 'dispatched', and texts the
 * customer an out-for-delivery SMS.
 */
import { config } from '../config';
import { receive, deleteMessage } from '../aws/sqsClient';
import * as orders from '../repositories/orderRepository';
import * as customers from '../repositories/customerRepository';
import { assignCourierToOrder } from '../services/deliveryService';
import { notifyCustomer, publishLifecycleEvent } from '../services/notificationService';
import { logger } from '../utils/logger';

interface DispatchJob {
  orderId: number;
  orderNo: string;
  zone: string;
}

// Mock distance estimate per zone (km) — a real system would geocode the address.
const ZONE_DISTANCE_KM: Record<string, number> = {
  Watthana: 3,
  Sathon: 4,
  'Bang Rak': 3.5,
  'Huai Khwang': 5,
  Chatuchak: 6,
  'Bang Kapi': 7,
};

export async function dispatchOne(job: DispatchJob): Promise<void> {
  const distance = ZONE_DISTANCE_KM[job.zone] ?? 5;
  const result = await assignCourierToOrder(job.orderId, job.zone, distance);
  if (!result.assigned) {
    logger.warn('no courier available; staying queued', { orderId: job.orderId, zone: job.zone });
    return;
  }

  await orders.updateOrderStatus(job.orderId, 'dispatched');
  await publishLifecycleEvent(job.orderId, 'out_for_delivery', {
    courierId: result.courier?.id,
    etaMinutes: result.etaMinutes,
  });

  const order = await orders.findOrderById(job.orderId);
  if (order) {
    const customer = await customers.findCustomerById(order.customer_id);
    if (customer) {
      await notifyCustomer({
        customerId: customer.id,
        orderId: order.id,
        phone: customer.phone,
        template: 'out_for_delivery',
        ctx: {
          orderNo: order.order_no,
          courierName: result.courier?.full_name,
          etaMinutes: result.etaMinutes,
        },
      });
    }
  }
  logger.info('order dispatched', { orderId: job.orderId, courierId: result.courier?.id });
}

export async function pollDispatchQueue(): Promise<void> {
  const messages = await receive(config.aws.sqsDispatchQueueUrl);
  for (const m of messages) {
    try {
      const body = JSON.parse(m.Body ?? '{}');
      if (!body || typeof body.orderId !== 'number') {
        await deleteMessage(config.aws.sqsDispatchQueueUrl, m.ReceiptHandle ?? '');
        continue;
      }
      await dispatchOne(body as DispatchJob);
      await deleteMessage(config.aws.sqsDispatchQueueUrl, m.ReceiptHandle ?? '');
    } catch (err) {
      logger.error('dispatch worker failed', { err: String(err) });
    }
  }
}
