/** Express application wiring (no listen() here — see server.ts). */
import express, { Application } from 'express';
import cors from 'cors';
import { router } from './routes';
import { notFound, errorHandler } from './middleware/errorHandler';

export function createApp(): Application {
  const app = express();
  app.use(cors());
  app.use(express.json());
  app.use('/api/v1', router);
  app.use(notFound);
  app.use(errorHandler);
  return app;
}
