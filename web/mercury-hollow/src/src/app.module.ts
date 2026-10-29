import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { ConfigModule, ConfigService } from '@nestjs/config';
import { AppController } from './app.controller';
import { AppService } from './app.service';
import { AuthModule } from './auth/auth.module';
import { ErrorModule } from './error/error.module';
import { ChallengeModule } from './challenge/challenge.module';
import { User } from './entities/user.entity';

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true,
      envFilePath: '.env',
    }),
    TypeOrmModule.forRootAsync({
      imports: [ConfigModule],
      useFactory: (config: ConfigService) => ({
        type: 'postgres',
        host: config.getOrThrow('APP_DB_HOST'),
        port: parseInt(config.getOrThrow('APP_DB_PORT'), 10),
        username: config.getOrThrow('APP_USER'),
        password: config.getOrThrow('APP_USER_PASS'),
        database: config.getOrThrow('APP_DB_NAME'),
        schema: config.get('APP_SCHEMA', 'app'),
        entities: [User],
        synchronize: true,
        logging: ['error'],
        extra: { application_name: 'bsides-api' },
      }),
      inject: [ConfigService],
    }),
    AuthModule,
    ChallengeModule,
    ErrorModule,
  ],
  controllers: [AppController],
  providers: [AppService],
})
export class AppModule {}
