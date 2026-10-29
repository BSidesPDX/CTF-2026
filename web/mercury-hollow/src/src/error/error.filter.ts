import {
  ExceptionFilter,
  Catch,
  ArgumentsHost,
  UnauthorizedException,
  ForbiddenException,
  HttpException,
  HttpStatus,
} from '@nestjs/common';
import { Request, Response } from 'express';

@Catch(UnauthorizedException, ForbiddenException)
export class AuthErrorFilter implements ExceptionFilter {
  catch(exception: HttpException, host: ArgumentsHost) {
    const ctx = host.switchToHttp();
    const response = ctx.getResponse<Response>();
    const request = ctx.getRequest<Request>();

    const status = exception.getStatus();
    const message = exception.message;

    // Log the error for debugging
    console.error(`Authentication Error: ${status} - ${message}`, {
      url: request.url,
      method: request.method,
      timestamp: new Date().toISOString(),
    });

    // Redirect to appropriate error page based on status code
    if (status === HttpStatus.UNAUTHORIZED) {
      return response.redirect('/error/401');
    } else if (status === HttpStatus.FORBIDDEN) {
      return response.redirect('/error/403');
    } else {
      return response.redirect('/error/auth-error');
    }
  }
}

@Catch()
export class GlobalErrorFilter implements ExceptionFilter {
  catch(exception: unknown, host: ArgumentsHost) {
    const ctx = host.switchToHttp();
    const response = ctx.getResponse<Response>();
    const request = ctx.getRequest<Request>();

    let status = HttpStatus.INTERNAL_SERVER_ERROR;
    let message = 'Internal Server Error';

    if (exception instanceof HttpException) {
      status = exception.getStatus();
      message = exception.message;
    }

    // Log the error
    console.error(`Global Error: ${status} - ${message}`, {
      url: request.url,
      method: request.method,
      timestamp: new Date().toISOString(),
      error: exception,
    });

    // For 401/403 errors, redirect to error pages
    if (status === HttpStatus.UNAUTHORIZED) {
      return response.redirect('/error/401');
    } else if (status === HttpStatus.FORBIDDEN) {
      return response.redirect('/error/403');
    }

    // For other errors, return JSON response
    response.status(status).json({
      statusCode: status,
      message: message,
      timestamp: new Date().toISOString(),
      path: request.url,
    });
  }
}
