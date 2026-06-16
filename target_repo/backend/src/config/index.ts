/**
 * Central configuration for the eleven-7 backend.
 * Everything tunable lives here and is read from the environment exactly once.
 * No other module should call process.env directly (context.md §2).
 */
import 'dotenv/config';

function env(key: string, fallback?: string): string {
  const v = process.env[key] ?? fallback;
  if (v === undefined) throw new Error(`Missing required env var: ${key}`);
  return v;
}

function envInt(key: string, fallback: number): number {
  const v = process.env[key];
  return v === undefined ? fallback : parseInt(v, 10);
}

function envBool(key: string, fallback: boolean): boolean {
  const v = process.env[key];
  if (v === undefined) return fallback;
  return ['1', 'true', 'yes'].includes(v.toLowerCase());
}

export interface AppConfig {
  env: string;
  port: number;
  db: {
    host: string;
    port: number;
    user: string;
    password: string;
    database: string;
    connectionLimit: number;
  };
  aws: {
    region: string;
    endpoint: string | undefined;
    accessKeyId: string;
    secretAccessKey: string;
    snsOrderTopicArn: string;
    sqsOrderQueueUrl: string;
    sqsDispatchQueueUrl: string;
    fakeMode: boolean;
  };
}

export const config: AppConfig = {
  env: env('NODE_ENV', 'development'),
  port: envInt('PORT', 4000),
  db: {
    host: env('DB_HOST', 'localhost'),
    port: envInt('DB_PORT', 3306),
    user: env('DB_USER', 'eleven7'),
    password: env('DB_PASSWORD', 'eleven7pass'),
    database: env('DB_NAME', 'eleven7'),
    connectionLimit: envInt('DB_CONNECTION_LIMIT', 10),
  },
  aws: {
    region: env('AWS_REGION', 'ap-southeast-1'),
    endpoint: process.env.AWS_ENDPOINT_URL || undefined,
    accessKeyId: env('AWS_ACCESS_KEY_ID', 'test'),
    secretAccessKey: env('AWS_SECRET_ACCESS_KEY', 'test'),
    snsOrderTopicArn: env(
      'SNS_ORDER_TOPIC_ARN',
      'arn:aws:sns:ap-southeast-1:000000000000:eleven7-order-events',
    ),
    sqsOrderQueueUrl: env(
      'SQS_ORDER_QUEUE_URL',
      'http://localhost:4566/000000000000/eleven7-order-processing',
    ),
    sqsDispatchQueueUrl: env(
      'SQS_DISPATCH_QUEUE_URL',
      'http://localhost:4566/000000000000/eleven7-delivery-dispatch',
    ),
    fakeMode: envBool('AWS_FAKE_MODE', false),
  },
};
