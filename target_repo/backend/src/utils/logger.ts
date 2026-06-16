/** Tiny structured logger. Single logging entry point for the whole backend. */
type Level = 'info' | 'warn' | 'error' | 'debug';

function emit(level: Level, msg: string, meta?: Record<string, unknown>): void {
  const line = {
    ts: new Date().toISOString(),
    level,
    msg,
    ...(meta ?? {}),
  };
  const sink = level === 'error' ? console.error : console.log;
  sink(JSON.stringify(line));
}

export const logger = {
  info: (msg: string, meta?: Record<string, unknown>): void => emit('info', msg, meta),
  warn: (msg: string, meta?: Record<string, unknown>): void => emit('warn', msg, meta),
  error: (msg: string, meta?: Record<string, unknown>): void => emit('error', msg, meta),
  debug: (msg: string, meta?: Record<string, unknown>): void => emit('debug', msg, meta),
};
