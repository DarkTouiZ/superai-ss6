/**
 * Order-processing worker — consumes the SQS order-processing queue. For each
 * message it confirms the order, sends the customer an SMS, and enqueues the
 * delivery-dispatch job. Mirrors a real async fulfillment pipeline.
 */
import { config } from '../config';
import { receive, deleteMessage, enqueue } from '../aws/sqsClient';
import * as orders from '../repositories/orderRepository';
import * as customers from '../repositories/customerRepository';
import { notifyCustomer, publishLifecycleEvent } from '../services/notificationService';
import { logger } from '../utils/logger';

interface OrderJob {
  orderId: number;
  orderNo: string;
  zone: string;
}

export async function processOne(job: OrderJob): Promise<void> {
  const order = await orders.findOrderById(job.orderId);
  if (!order) {
    logger.warn('order job for missing order', { orderId: job.orderId });
    return;
  }
  await orders.updateOrderStatus(order.id, 'confirmed');
  await publishLifecycleEvent(order.id, 'order_confirmed', { orderNo: order.order_no });

  const customer = await customers.findCustomerById(order.customer_id);
  if (customer) {
    await notifyCustomer({
      customerId: customer.id,
      orderId: order.id,
      phone: customer.phone,
      template: 'order_confirmed',
      ctx: { orderNo: order.order_no, totalSatang: order.total_satang },
    });
  }

  // Hand off to dispatch.
  await enqueue(config.aws.sqsDispatchQueueUrl, {
    orderId: order.id,
    orderNo: order.order_no,
    zone: job.zone,
  });
  logger.info('order processed -> dispatch enqueued', { orderId: order.id });
}

export async function pollOrderQueue(): Promise<void> {
  const messages = await receive(config.aws.sqsOrderQueueUrl);
  for (const m of messages) {
    try {
      const body = JSON.parse(m.Body ?? '{}');
      // Skip anything that isn't a well-formed order job (e.g. stray SNS envelopes).
      if (!body || typeof body.orderId !== 'number') {
        logger.warn('order worker skipping non-order message', { body: m.Body?.slice(0, 80) });
        await deleteMessage(config.aws.sqsOrderQueueUrl, m.ReceiptHandle ?? '');
        continue;
      }
      await processOne(body as OrderJob);
      await deleteMessage(config.aws.sqsOrderQueueUrl, m.ReceiptHandle ?? '');
    } catch (err) {
      logger.error('order worker failed', { err: String(err) });
    }
  }
}
