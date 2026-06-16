/**
 * Service registry — eleven-7's internal microservices each carry a product
 * codename, the way a real platform names its services. Every domain service
 * references its entry here so logs, the SNS/SQS resource names, and the
 * /api/v1/services catalog all speak the same branded language.
 *
 * (These are mock/branded names for a mock app — no real services are deployed.)
 */
export interface ServiceInfo {
  key: string;        // stable internal key
  codename: string;   // branded product name used in logs / catalog
  domain: string;     // what it owns
  topicSuffix: string; // used to derive SNS/SQS resource names
}

export const SERVICES: Record<string, ServiceInfo> = {
  catalog: {
    key: 'catalog',
    codename: 'ShelfScan',
    domain: 'product catalog & search',
    topicSuffix: 'shelfscan',
  },
  pricing: {
    key: 'pricing',
    codename: 'PricePilot',
    domain: 'cart pricing, delivery fees & points accrual',
    topicSuffix: 'pricepilot',
  },
  orders: {
    key: 'orders',
    codename: 'OrderForge',
    domain: 'order placement & lifecycle',
    topicSuffix: 'orderforge',
  },
  delivery: {
    key: 'delivery',
    codename: 'FleetDash',
    domain: 'courier assignment & delivery tracking',
    topicSuffix: 'fleetdash',
  },
  notifications: {
    key: 'notifications',
    codename: 'PulseNotify',
    domain: 'SMS + SNS customer notifications',
    topicSuffix: 'pulsenotify',
  },
  payments: {
    key: 'payments',
    codename: 'PaySwift',
    domain: 'authorize / capture / refund',
    topicSuffix: 'payswift',
  },
  promotions: {
    key: 'promotions',
    codename: 'PerksEngine',
    domain: 'coupons & ALL Member points',
    topicSuffix: 'perksengine',
  },
  support: {
    key: 'support',
    codename: 'CareDesk',
    domain: 'returns & support tickets',
    topicSuffix: 'caredesk',
  },
  inventory: {
    key: 'inventory',
    codename: 'StockKeeper',
    domain: 'per-store stock, transfers & low-stock alerts',
    topicSuffix: 'stockkeeper',
  },
};

/** Branded codename for a service key (falls back to the key itself). */
export function serviceName(key: string): string {
  return SERVICES[key]?.codename ?? key;
}

/** The full catalog, for the /api/v1/services endpoint. */
export function serviceCatalog(): ServiceInfo[] {
  return Object.values(SERVICES);
}
