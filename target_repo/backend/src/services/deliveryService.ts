/**
 * Delivery service — greedy courier assignment by zone + a simple ETA estimate.
 * Pure assignment logic (estimateEta) is unit-tested; I/O is delegated to repos.
 */
import { findAvailableCourierInZone, setCourierStatus } from '../repositories/courierRepository';
import { assignCourier, findDeliveryByOrder } from '../repositories/deliveryRepository';
import { Courier } from '../types/models';

/** Rough ETA: base + per-km, by vehicle. Pure, deterministic, testable. */
export function estimateEta(distanceKm: number, vehicle: Courier['vehicle']): number {
  const perKm: Record<Courier['vehicle'], number> = {
    motorbike: 2.5,
    bicycle: 5,
    car: 3,
    van: 3.5,
  };
  const base = 8; // minutes of prep/handover
  return Math.max(10, Math.round(base + distanceKm * perKm[vehicle]));
}

export interface AssignmentResult {
  assigned: boolean;
  courier?: Courier;
  etaMinutes?: number;
}

/**
 * Try to assign an available courier in the order's zone to its delivery.
 * Returns assigned:false when no courier is free (the delivery stays queued).
 */
export async function assignCourierToOrder(
  orderId: number,
  zone: string,
  distanceKm: number,
): Promise<AssignmentResult> {
  const delivery = await findDeliveryByOrder(orderId);
  if (!delivery) throw new Error(`no delivery row for order ${orderId}`);

  const courier = await findAvailableCourierInZone(zone);
  if (!courier) return { assigned: false };

  const eta = estimateEta(distanceKm, courier.vehicle);
  await assignCourier(delivery.id, courier.id, eta);
  await setCourierStatus(courier.id, 'on_delivery');
  return { assigned: true, courier, etaMinutes: eta };
}
