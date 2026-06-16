/**
 * PaySwift — payment lifecycle (authorize -> capture -> refund) + refund requests.
 * Pure helpers (refundableAmount, nextStatus) are unit-tested; writes go through
 * the payment repository. Publishes a lifecycle event via PulseNotify/SNS.
 */
import { serviceName } from './registry';
import * as paymentsRepo from '../repositories/paymentRepository';
import { publishLifecycleEvent } from './notificationService';
import { logger } from '../utils/logger';
import { ValidationError } from './errors';

export const SERVICE = serviceName('payments'); // "PaySwift"

export type PaymentStatus = 'pending' | 'authorized' | 'captured' | 'failed' | 'refunded';

export interface Payment {
  id: number;
  order_id: number;
  status: PaymentStatus;
  amount_satang: number;
}

/** Pure: how much can still be refunded on a payment. */
export function refundableAmount(payment: Payment, alreadyRefundedSatang: number): number {
  if (payment.status !== 'captured') return 0;
  return Math.max(0, payment.amount_satang - Math.max(0, alreadyRefundedSatang));
}

/** Pure: legal next status transitions for a payment. */
export function canTransition(from: PaymentStatus, to: PaymentStatus): boolean {
  const allowed: Record<PaymentStatus, PaymentStatus[]> = {
    pending: ['authorized', 'failed'],
    authorized: ['captured', 'failed'],
    captured: ['refunded'],
    failed: [],
    refunded: [],
  };
  return allowed[from].includes(to);
}

export async function capture(paymentId: number): Promise<void> {
  const payment = await paymentsRepo.findById(paymentId);
  if (!payment) throw new ValidationError(`unknown payment ${paymentId}`);
  if (!canTransition(payment.status, 'captured')) {
    throw new ValidationError(`cannot capture a ${payment.status} payment (must be authorized first)`);
  }
  await paymentsRepo.setStatus(paymentId, 'captured');
  await paymentsRepo.recordEvent(paymentId, 'captured', payment.amount_satang, payment.provider_ref);
  await publishLifecycleEvent(payment.order_id, 'payment_captured', { service: SERVICE, paymentId });
  logger.info('payment captured', { service: SERVICE, paymentId });
}

/** Request and process a refund (full or partial). */
export async function refund(
  orderId: number,
  paymentId: number,
  amountSatang: number,
  reason: string,
): Promise<number> {
  const payment = await paymentsRepo.findById(paymentId);
  if (!payment) throw new ValidationError(`unknown payment ${paymentId}`);
  const already = await paymentsRepo.totalRefunded(paymentId);
  const max = refundableAmount(payment, already);
  const amount = Math.min(Math.max(0, Math.trunc(amountSatang)), max);
  if (amount <= 0) {
    throw new ValidationError('nothing refundable on this payment (must be captured, not already fully refunded)');
  }

  const refundId = await paymentsRepo.createRefund(orderId, paymentId, amount, reason);
  await paymentsRepo.recordEvent(paymentId, 'refunded', amount, payment.provider_ref);
  if (amount >= payment.amount_satang) {
    await paymentsRepo.setStatus(paymentId, 'refunded');
  }
  await publishLifecycleEvent(orderId, 'payment_refunded', { service: SERVICE, amount });
  logger.info('payment refunded', { service: SERVICE, orderId, amount });
  return refundId;
}
