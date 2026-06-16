/** HTTP entry point for the eleven-7 API. */
import { createApp } from './app';
import { config } from './config';
import { logger } from './utils/logger';
import { closePool } from './db/pool';

const app = createApp();
const server = app.listen(config.port, () => {
  logger.info('eleven7-api listening', { port: config.port, env: config.env });
});

async function shutdown(signal: string): Promise<void> {
  logger.info('shutting down', { signal });
  server.close(async () => {
    await closePool();
    process.exit(0);
  });
}

process.on('SIGTERM', () => void shutdown('SIGTERM'));
process.on('SIGINT', () => void shutdown('SIGINT'));
