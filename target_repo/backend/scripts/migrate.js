/**
 * Minimal migration runner: applies every .sql file in db/migrations in order.
 * Usage: node scripts/migrate.js   (reads DB_* from the environment / .env)
 */
const fs = require('fs');
const path = require('path');
const mysql = require('mysql2/promise');
require('dotenv/config');

async function main() {
  const dir = path.join(__dirname, '..', 'db', 'migrations');
  const files = fs.readdirSync(dir).filter((f) => f.endsWith('.sql')).sort();

  const conn = await mysql.createConnection({
    host: process.env.DB_HOST || 'localhost',
    port: Number(process.env.DB_PORT || 3306),
    user: process.env.DB_USER || 'root',
    password: process.env.DB_PASSWORD || '',
    multipleStatements: true,
  });

  for (const f of files) {
    const sql = fs.readFileSync(path.join(dir, f), 'utf8');
    process.stdout.write(`applying ${f} ... `);
    await conn.query(sql);
    console.log('ok');
  }
  await conn.end();
  console.log('migrations complete');
}

main().catch((err) => {
  console.error('migration failed:', err.message);
  process.exit(1);
});
