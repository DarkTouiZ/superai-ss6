/**
 * SQS wrapper — enqueue/poll/delete for the order-processing and delivery-dispatch
 * queues. The only module that talks to Amazon SQS (context.md §5).
 */
import {
  SQSClient,
  SendMessageCommand,
  ReceiveMessageCommand,
  DeleteMessageCommand,
  Message,
} from '@aws-sdk/client-sqs';
import { config } from '../config';
import { logger } from '../utils/logger';

let client: SQSClient | null = null;

// In-process queues used only when AWS_FAKE_MODE=true (no LocalStack needed).
const fakeQueues: Record<string, Array<{ MessageId: string; Body: string; ReceiptHandle: string }>> = {};

function sqs(): SQSClient {
  if (!client) {
    client = new SQSClient({
      region: config.aws.region,
      endpoint: config.aws.endpoint,
      credentials: {
        accessKeyId: config.aws.accessKeyId,
        secretAccessKey: config.aws.secretAccessKey,
      },
    });
  }
  return client;
}

export async function enqueue(queueUrl: string, body: Record<string, unknown>): Promise<string> {
  if (config.aws.fakeMode) {
    const id = `fake-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    (fakeQueues[queueUrl] ??= []).push({ MessageId: id, Body: JSON.stringify(body), ReceiptHandle: id });
    logger.info('sqs.enqueue (faked)', { queueUrl, id });
    return id;
  }
  const out = await sqs().send(
    new SendMessageCommand({ QueueUrl: queueUrl, MessageBody: JSON.stringify(body) }),
  );
  return out.MessageId ?? 'unknown';
}

export async function receive(queueUrl: string, max = 5): Promise<Message[]> {
  if (config.aws.fakeMode) {
    const q = fakeQueues[queueUrl] ?? [];
    return q.splice(0, max);
  }
  const out = await sqs().send(
    new ReceiveMessageCommand({
      QueueUrl: queueUrl,
      MaxNumberOfMessages: max,
      WaitTimeSeconds: 5, // long polling
    }),
  );
  return out.Messages ?? [];
}

export async function deleteMessage(queueUrl: string, receiptHandle: string): Promise<void> {
  if (config.aws.fakeMode) return; // already removed by receive()
  await sqs().send(new DeleteMessageCommand({ QueueUrl: queueUrl, ReceiptHandle: receiptHandle }));
}
