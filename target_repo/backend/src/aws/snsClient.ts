/**
 * SNS wrapper — the ONLY module that talks to Amazon SNS (context.md §5: all AWS
 * access is funneled through src/aws/*). Points at LocalStack by default; set
 * AWS_FAKE_MODE=true to short-circuit to an in-process fake (no network at all).
 */
import { SNSClient, PublishCommand } from '@aws-sdk/client-sns';
import { config } from '../config';
import { logger } from '../utils/logger';

let client: SNSClient | null = null;

function sns(): SNSClient {
  if (!client) {
    client = new SNSClient({
      region: config.aws.region,
      endpoint: config.aws.endpoint, // LocalStack URL; undefined => real AWS
      credentials: {
        accessKeyId: config.aws.accessKeyId,
        secretAccessKey: config.aws.secretAccessKey,
      },
    });
  }
  return client;
}

export interface PublishResult {
  messageId: string;
  faked: boolean;
}

/** Publish an order-event message to the eleven-7 order-events topic. */
export async function publishOrderEvent(
  payload: Record<string, unknown>,
  attributes: Record<string, string> = {},
): Promise<PublishResult> {
  if (config.aws.fakeMode) {
    const messageId = `fake-sns-${Date.now()}`;
    logger.info('sns.publish (faked)', { topic: config.aws.snsOrderTopicArn, messageId });
    return { messageId, faked: true };
  }
  const out = await sns().send(
    new PublishCommand({
      TopicArn: config.aws.snsOrderTopicArn,
      Message: JSON.stringify(payload),
      MessageAttributes: Object.fromEntries(
        Object.entries(attributes).map(([k, v]) => [k, { DataType: 'String', StringValue: v }]),
      ),
    }),
  );
  return { messageId: out.MessageId ?? 'unknown', faked: false };
}
