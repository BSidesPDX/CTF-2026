import { Controller, Get, Render, Req, Res } from '@nestjs/common';
import type { Request, Response } from 'express';

@Controller('error')
export class ErrorController {
  @Get('401')
  @Render('error')
  async unauthorized(@Req() req: Request, @Res() res: Response) {
    return {
      errorCode: 401,
      errorMessage: 'Unauthorized',
      timestamp: new Date().toISOString(),
    };
  }

  @Get('403')
  @Render('error')
  async forbidden(@Req() req: Request, @Res() res: Response) {
    return {
      errorCode: 403,
      errorMessage: 'Forbidden',
      timestamp: new Date().toISOString(),
    };
  }

  @Get('auth-error')
  @Render('error')
  async authError(@Req() req: Request, @Res() res: Response) {
    return {
      errorCode: 401,
      errorMessage: 'Authentication Error',
      timestamp: new Date().toISOString(),
    };
  }
}
