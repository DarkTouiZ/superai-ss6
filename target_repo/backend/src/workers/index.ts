/** Worker entry point — long-polls both SQS queues in a loop. */
import { pollOrderQueue } from './orderWorker';
import { pollDispatchQueue } from './dispatchWorker';
import { logger } from '../utils/logger';
import { closePool } from '../db/pool';

let running = true;

async function loop(): Promise<void> {
  logger.info('eleven7 workers started');
  while (running) {
    await pollOrderQueue();
    await pollDispatchQueue();
    // small breather between poll cycles (LocalStack/fake mode)
    await new Promise((r) => setTimeout(r, 1000));
  }
}

async function stop(signal: string): Promise<void> {
  logger.info('workers stopping', { signal });
  running = false;
  await closePool();
  process.exit(0);
}

process.on('SIGTERM', () => void stop('SIGTERM'));
process.on('SIGINT', () => void stop('SIGINT'));

loop().catch((err) => {
  logger.error('worker loop crashed', { err: String(err) });
  process.exit(1);
});
