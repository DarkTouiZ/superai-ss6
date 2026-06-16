/** Wrap a zod schema as Express middleware that validates req.body. */
import { Request, Response, NextFunction } from 'express';
import { ZodSchema } from 'zod';

export function validateBody<T>(schema: ZodSchema<T>) {
  return (req: Request, _res: Response, next: NextFunction): void => {
    const parsed = schema.parse(req.body);
    req.body = parsed;
    next();
  };
}
