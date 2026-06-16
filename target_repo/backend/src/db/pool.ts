/**
 * MySQL connection pool — the SINGLE place the backend talks to MySQL.
 * Repositories use `query`/`withTransaction`; nothing else opens connections.
 * context.md §4: all persistence goes through the repository layer over this pool.
 */
import mysql, { Pool, PoolConnection, RowDataPacket, ResultSetHeader } from 'mysql2/promise';
import { config } from '../config';
import { logger } from '../utils/logger';

let pool: Pool | null = null;

export function getPool(): Pool {
  if (!pool) {
    pool = mysql.createPool({
      host: config.db.host,
      port: config.db.port,
      user: config.db.user,
      password: config.db.password,
      database: config.db.database,
      connectionLimit: config.db.connectionLimit,
      waitForConnections: true,
      namedPlaceholders: true,
      timezone: 'Z',
    });
    logger.info('mysql pool created', { host: config.db.host, db: config.db.database });
  }
  return pool;
}

// mysql2's execute() overloads don't type named-placeholder objects; values are
// validated at runtime (namedPlaceholders: true). Loosen the param type here.
type SqlParams = Record<string, unknown> | unknown[];

/** Parameterized query helper. Always pass params — never interpolate SQL strings. */
export async function query<T extends RowDataPacket[]>(
  sql: string,
  params?: SqlParams,
): Promise<T> {
  const [rows] = await getPool().execute<T>(sql, params as never);
  return rows;
}

/** Write helper returning the insert/affected metadata. */
export async function execute(
  sql: string,
  params?: SqlParams,
): Promise<ResultSetHeader> {
  const [result] = await getPool().execute<ResultSetHeader>(sql, params as never);
  return result;
}

/** Run `fn` inside a transaction; commit on success, rollback on throw. */
export async function withTransaction<T>(
  fn: (conn: PoolConnection) => Promise<T>,
): Promise<T> {
  const conn = await getPool().getConnection();
  try {
    await conn.beginTransaction();
    const result = await fn(conn);
    await conn.commit();
    return result;
  } catch (err) {
    await conn.rollback();
    throw err;
  } finally {
    conn.release();
  }
}

export async function closePool(): Promise<void> {
  if (pool) {
    await pool.end();
    pool = null;
  }
}
