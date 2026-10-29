import connectPgSimple from 'connect-pg-simple';
import session from 'express-session';
import type { Store } from 'express-session';

const PostgresSessionStore = connectPgSimple(session);

export function createPostgresSessionStore(): Store {
  return new PostgresSessionStore({
    conObject: {
      host: requiredEnvironment('APP_DB_HOST'),
      port: Number(requiredEnvironment('APP_DB_PORT')),
      user: requiredEnvironment('APP_USER'),
      password: requiredEnvironment('APP_USER_PASS'),
      database: requiredEnvironment('APP_DB_NAME'),
    },
    schemaName: process.env.APP_SCHEMA || 'app',
    tableName: 'challenge_sessions',
    createTableIfMissing: true,
    ttl: sessionLifetimeSeconds(),
  });
}

function requiredEnvironment(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(`${name} is required`);
  }
  return value;
}

function sessionLifetimeSeconds(): number {
  const hours = Number(process.env.SESSION_MAX_AGE_HOURS || 72);
  return Number.isFinite(hours) && hours > 0 ? hours * 60 * 60 : 72 * 60 * 60;
}
