/** Service catalog endpoint — lists eleven-7's branded internal services. */
import { Request, Response } from 'express';
import { serviceCatalog } from '../services/registry';

export function getServices(_req: Request, res: Response): void {
  res.json({ services: serviceCatalog() });
}
