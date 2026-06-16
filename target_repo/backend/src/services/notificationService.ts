/**
 * Notification service — renders SMS bodies from templates and sends them via the
 * AWS SMS wrapper, recording every send in the notifications outbox. Business logic
 * only; all AWS access goes through src/aws/*, all DB access through repositories.
 */
import { sendSms } from '../aws/smsClient';
import { publishOrderEvent } from '../aws/snsClient';
import { recordNotification } from '../repositories/notificationRepository';
import { formatTHB } from '../utils/money';
import { logger } from '../utils/logger';

export type SmsTemplate =
  | 'order_confirmed'
  | 'out_for_delivery'
  | 'delivered'
  | 'order_cancelled';

interface SmsContext {
  orderNo: string;
  totalSatang?: number;
  courierName?: string;
  etaMinutes?: number;
}

export function renderSms(template: SmsTemplate, ctx: SmsContext): string {
  switch (template) {
    case 'order_confirmed':
      return `eleven-7: Order ${ctx.orderNo} confirmed. Total ${formatTHB(ctx.totalSatang ?? 0)}.`;
    case 'out_for_delivery':
      return `eleven-7: Your order is on the way! Courier ${ctx.courierName ?? 'rider'}, ETA ${ctx.etaMinutes ?? '?'} min.`;
    case 'delivered':
      return `eleven-7: Order ${ctx.orderNo} delivered. Enjoy!`;
    case 'order_cancelled':
      return `eleven-7: Order ${ctx.orderNo} was cancelled and refunded.`;
  }
}

/** Send a customer SMS and persist it to the outbox. */
export async function notifyCustomer(args: {
  customerId: number;
  orderId: number;
  phone: string;
  template: SmsTemplate;
  ctx: SmsContext;
}): Promise<void> {
  const body = renderSms(args.template, args.ctx);
  try {
    const res = await sendSms(args.phone, body);
    await recordNotification({
      customer_id: args.customerId,
      order_id: args.orderId,
      channel: 'sms',
      template: args.template,
      destination: args.phone,
      body,
      status: 'sent',
      provider_message_id: res.messageId,
    });
  } catch (err) {
    logger.error('notifyCustomer failed', { err: String(err), template: args.template });
    await recordNotification({
      customer_id: args.customerId,
      order_id: args.orderId,
      channel: 'sms',
      template: args.template,
      destination: args.phone,
      body,
      status: 'failed',
      provider_message_id: null,
    });
  }
}

/** Fan-out an order lifecycle event to the SNS topic (for internal subscribers). */
export async function publishLifecycleEvent(
  orderId: number,
  event: string,
  extra: Record<string, unknown> = {},
): Promise<void> {
  await publishOrderEvent({ orderId, event, ...extra }, { event });
}
