/**
 * Shared domain errors. A ValidationError signals a business-rule violation or bad
 * input (mapped to HTTP 422 by the error handler) rather than an unexpected crash.
 */
export class ValidationError extends Error {}
