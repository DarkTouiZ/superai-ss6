#!/bin/bash
# Provision eleven-7's SNS topic + SQS queues in LocalStack on startup, and wire
# the order-events topic to fan out to the processing queue.
set -euo pipefail
export AWS_DEFAULT_REGION=ap-southeast-1
AWSLOCAL="awslocal"

echo "[init-aws] creating SQS queues"
ORDER_Q_URL=$($AWSLOCAL sqs create-queue --queue-name eleven7-order-processing --query QueueUrl --output text)
DISPATCH_Q_URL=$($AWSLOCAL sqs create-queue --queue-name eleven7-delivery-dispatch --query QueueUrl --output text)

echo "[init-aws] creating SNS topic (order-events; for event subscribers only —"
echo "           the work queue is fed by direct SQS enqueue, NOT by this topic)"
TOPIC_ARN=$($AWSLOCAL sns create-topic --name eleven7-order-events --query TopicArn --output text)

echo "[init-aws] done:"
echo "  TOPIC_ARN=$TOPIC_ARN"
echo "  ORDER_Q_URL=$ORDER_Q_URL"
echo "  DISPATCH_Q_URL=$DISPATCH_Q_URL"
