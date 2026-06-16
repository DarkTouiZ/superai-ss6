/** Customer + address reads. */
import { RowDataPacket } from 'mysql2/promise';
import { query } from '../db/pool';
import { Address, Customer } from '../types/models';

type CustomerRow = Customer & RowDataPacket;
type AddressRow = Address & RowDataPacket;

export async function findCustomerById(id: number): Promise<Customer | null> {
  const rows = await query<CustomerRow[]>(
    `SELECT id, full_name, phone, email, loyalty_tier, points_balance, marketing_opt_in
       FROM customers WHERE id = :id`,
    { id },
  );
  return rows[0] ?? null;
}

export async function findAddressById(id: number): Promise<Address | null> {
  const rows = await query<AddressRow[]>(
    `SELECT id, customer_id, label, line1, line2, district, city, postal_code, is_default
       FROM addresses WHERE id = :id`,
    { id },
  );
  return rows[0] ?? null;
}

/** ALL Member: award points to a customer (1 point per 10 THB by default). */
export async function addPoints(customerId: number, points: number): Promise<void> {
  await query(
    `UPDATE customers SET points_balance = points_balance + :points WHERE id = :customerId`,
    { points, customerId },
  );
}
