/** Courier reads + status updates used by the dispatch service. */
import { RowDataPacket } from 'mysql2/promise';
import { query } from '../db/pool';
import { Courier, CourierStatus } from '../types/models';

type CourierRow = Courier & RowDataPacket;

/** Find an available courier in a zone, best-rated first (greedy assignment). */
export async function findAvailableCourierInZone(zone: string): Promise<Courier | null> {
  const rows = await query<CourierRow[]>(
    `SELECT id, full_name, phone, vehicle, status, zone, rating
       FROM couriers
      WHERE status = 'available' AND zone = :zone
      ORDER BY rating DESC
      LIMIT 1`,
    { zone },
  );
  return rows[0] ?? null;
}

export async function setCourierStatus(id: number, status: CourierStatus): Promise<void> {
  await query(`UPDATE couriers SET status = :status WHERE id = :id`, { status, id });
}

export async function listCouriers(): Promise<Courier[]> {
  return query<CourierRow[]>(
    `SELECT id, full_name, phone, vehicle, status, zone, rating FROM couriers ORDER BY zone, rating DESC`,
  );
}
