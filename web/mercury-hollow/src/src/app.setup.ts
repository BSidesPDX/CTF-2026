import { ValidationPipe } from '@nestjs/common';
import { NestExpressApplication } from '@nestjs/platform-express';
import cookieParser from 'cookie-parser';
import session from 'express-session';
import type { Store } from 'express-session';
import helpers from 'handlebars-helpers';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import passport from 'passport';
import * as hbs from 'hbs';

export interface ApplicationSetupOptions {
  sessionStore?: Store;
}

export function configureApplication(
  app: NestExpressApplication,
  options: ApplicationSetupOptions = {},
): void {
  const viewsDir = firstExistingPath([
    join(process.cwd(), 'src', 'views'),
    join(process.cwd(), 'views'),
    join(__dirname, '..', 'views'),
  ]);
  const partialsDir = join(viewsDir, 'partials');
  const imageAssetsDir = join(process.cwd(), 'public', 'images');

  app.setBaseViewsDir(viewsDir);
  app.setViewEngine('hbs');

  if (existsSync(imageAssetsDir)) {
    app.useStaticAssets(imageAssetsDir, { prefix: '/images/' });
  }

  registerPartials(partialsDir);
  helpers({ handlebars: hbs.handlebars });

  app.use(cookieParser());
  const corsOrigins = process.env.CORS_ORIGIN?.split(',')
    .map((origin) => origin.trim())
    .filter(Boolean);
  if (corsOrigins?.length) {
    app.enableCors({ origin: corsOrigins, credentials: true });
  }
  app.useGlobalPipes(
    new ValidationPipe({
      whitelist: true,
      forbidNonWhitelisted: true,
      transform: true,
    }),
  );

  const production = process.env.NODE_ENV === 'production';
  const sessionSecret = process.env.SESSION_SECRET;
  if (production && !sessionSecret) {
    throw new Error('SESSION_SECRET is required in production');
  }
  if (production && !process.env.JWT_SECRET) {
    throw new Error('JWT_SECRET is required in production');
  }

  if (production) {
    app.set('trust proxy', 1);
  }

  app.use(
    session({
      name: 'bside.sid',
      secret: sessionSecret || 'development-session-secret',
      store: options.sessionStore,
      resave: false,
      saveUninitialized: false,
      cookie: {
        secure: production ? 'auto' : false,
        httpOnly: true,
        sameSite: 'lax',
        maxAge: sessionLifetimeMs(),
      },
    }),
  );

  app.use(passport.initialize());
  app.use(passport.session());
}

function registerPartials(partialsDir: string): void {
  try {
    hbs.registerPartials(partialsDir);
  } catch {
    if (!existsSync(partialsDir)) {
      return;
    }

    for (const file of readdirSync(partialsDir)) {
      if (file.endsWith('.hbs')) {
        const name = file.replace('.hbs', '');
        const content = readFileSync(join(partialsDir, file), 'utf8');
        hbs.handlebars.registerPartial(name, content);
      }
    }
  }
}

function sessionLifetimeMs(): number {
  const hours = Number(process.env.SESSION_MAX_AGE_HOURS || 72);
  return Number.isFinite(hours) && hours > 0
    ? hours * 60 * 60 * 1000
    : 72 * 60 * 60 * 1000;
}

function firstExistingPath(paths: string[]): string {
  const found = paths.find((path) => existsSync(path));
  return found ?? paths[0];
}
