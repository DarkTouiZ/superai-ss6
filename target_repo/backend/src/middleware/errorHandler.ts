/** Central Express error handler + 404. Keeps controllers free of error plumbing. */
import { Request, Response, NextFunction } from 'express';
import { ZodError } from 'zod';
import { ValidationError } from '../services/orderService';
import { logger } from '../utils/logger';

export function notFound(_req: Request, res: Response): void {
  res.status(404).json({ error: 'not_found' });
}

export function errorHandler(
  err: unknown,
  _req: Request,
  res: Response,
  _next: NextFunction,
): void {
  if (err instanceof ZodError) {
    res.status(400).json({ error: 'invalid_request', details: err.flatten() });
    return;
  }
  if (err instanceof ValidationError) {
    res.status(422).json({ error: 'unprocessable', message: err.message });
    return;
  }
  logger.error('unhandled error', { err: String(err) });
  res.status(500).json({ error: 'internal_error' });
}
