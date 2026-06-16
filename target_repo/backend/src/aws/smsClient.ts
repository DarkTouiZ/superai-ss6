/**
 * SMS wrapper — sends transactional SMS to customers via SNS Publish (PhoneNumber).
 * Same LocalStack/fake behavior as snsClient. This is the only place SMS is sent.
 */
import { SNSClient, PublishCommand } from '@aws-sdk/client-sns';
import { config } from '../config';
import { logger } from '../utils/logger';

let client: SNSClient | null = null;

function sns(): SNSClient {
  if (!client) {
    client = new SNSClient({
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

export interface SmsResult {
  messageId: string;
  faked: boolean;
}

/** Send a plain-text SMS to an E.164 phone number. */
export async function sendSms(phoneE164: string, body: string): Promise<SmsResult> {
  if (config.aws.fakeMode) {
    const messageId = `fake-sms-${Date.now()}`;
    logger.info('sms.send (faked)', { to: phoneE164, body });
    return { messageId, faked: true };
  }
  const out = await sns().send(
    new PublishCommand({
      PhoneNumber: phoneE164,
      Message: body,
      MessageAttributes: {
        'AWS.SNS.SMS.SMSType': { DataType: 'String', StringValue: 'Transactional' },
        'AWS.SNS.SMS.SenderID': { DataType: 'String', StringValue: 'eleven7' },
      },
    }),
  );
  return { messageId: out.MessageId ?? 'unknown', faked: false };
}
