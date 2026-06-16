/** Domain model types for eleven-7. Mirror the MySQL schema (db/migrations/001_schema.sql). */

export type OrderStatus =
  | 'pending'
  | 'confirmed'
  | 'preparing'
  | 'dispatched'
  | 'delivered'
  | 'cancelled';

export type DeliveryStatus =
  | 'queued'
  | 'assigned'
  | 'picked_up'
  | 'en_route'
  | 'delivered'
  | 'failed';

export type CourierStatus = 'offline' | 'available' | 'on_delivery' | 'on_break';
export type LoyaltyTier = 'standard' | 'silver' | 'gold' | 'platinum';

export interface Customer {
  id: number;
  full_name: string;
  phone: string;
  email: string | null;
  loyalty_tier: LoyaltyTier;
  marketing_opt_in: boolean;
}

export interface Address {
  id: number;
  customer_id: number;
  label: string;
  line1: string;
  line2: string | null;
  district: string;
  city: string;
  postal_code: string;
  is_default: boolean;
}

export interface Product {
  id: number;
  category_id: number;
  sku: string;
  name: string;
  description: string | null;
  unit: string;
  price_satang: number;
  is_active: boolean;
}

export interface Courier {
  id: number;
  full_name: string;
  phone: string;
  vehicle: 'motorbike' | 'bicycle' | 'car' | 'van';
  status: CourierStatus;
  zone: string;
  rating: number;
}

export interface OrderItem {
  id?: number;
  order_id?: number;
  product_id: number;
  product_name: string;
  qty: number;
  unit_price_satang: number;
  line_total_satang: number;
}

export interface Order {
  id: number;
  order_no: string;
  customer_id: number;
  address_id: number;
  status: OrderStatus;
  subtotal_satang: number;
  delivery_fee_satang: number;
  discount_satang: number;
  total_satang: number;
  placed_at: string;
  items?: OrderItem[];
}

export interface Delivery {
  id: number;
  order_id: number;
  courier_id: number | null;
  status: DeliveryStatus;
  eta_minutes: number | null;
}

/** A request to create an order (validated at the controller edge). */
export interface NewOrderInput {
  customer_id: number;
  address_id: number;
  lines: Array<{ product_id: number; qty: number }>;
  discount_satang?: number;
}
