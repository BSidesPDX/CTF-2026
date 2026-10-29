import { Module } from '@nestjs/common';
import { APP_FILTER } from '@nestjs/core';
import { ErrorController } from './error.controller';
import { AuthErrorFilter, GlobalErrorFilter } from './error.filter';

@Module({
  controllers: [ErrorController],
  providers: [
    {
      provide: APP_FILTER,
      useClass: AuthErrorFilter,
    },
    {
      provide: APP_FILTER,
      useClass: GlobalErrorFilter,
    },
  ],
})
export class ErrorModule {}
