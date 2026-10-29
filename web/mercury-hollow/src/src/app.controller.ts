import {
  Controller,
  Get,
  Post,
  Req,
  Res,
  UseGuards,
  Render,
} from '@nestjs/common';
import type { Request, Response } from 'express';
import { AuthService } from './auth/auth.service';
import { JwtAuthGuard } from './auth/guards/jwt-auth.guard';

@Controller()
export class AppController {
  constructor(private authService: AuthService) {}

  @Get()
  @Render('landing')
  landingPage() {
    return {
      title: 'Ellingson Mineral Corporation',
      subtitle: 'Deep-Sea Mining & Extraction',
      navigationLinks: [
        { text: 'Employee Portal', url: '/login' },
        { text: 'About Us', url: '#about' },
        { text: 'Services', url: '#services' },
        { text: 'Contact', url: '#contact' },
      ],
    };
  }

  @Get('portal')
  async portal(@Req() req: Request, @Res() res: Response) {
    try {
      // Try to extract and validate the JWT token from cookies
      const token = req.cookies?.token;

      if (!token) {
        // No token, redirect to login
        return res.redirect('/login');
      }

      // Try to validate the token by checking if we can find the user
      // We'll use a simple approach by trying to decode the token
      const jwt = require('jsonwebtoken');
      const secret = process.env.JWT_SECRET || 'your-secret-key';

      try {
        const decoded = jwt.verify(token, secret);
        const user = await this.authService.validateTeam(decoded.teamName);

        if (user) {
          // User is authenticated, redirect to secret page
          return res.redirect('/secret');
        } else {
          // Invalid user, redirect to login
          return res.redirect('/login');
        }
      } catch (error) {
        // Invalid token, redirect to login
        return res.redirect('/login');
      }
    } catch (error) {
      // Any error, redirect to login
      return res.redirect('/login');
    }
  }

  @Get('logout')
  @Post('logout')
  async logout(@Res() res: Response) {
    try {
      // Call auth service logout method
      await this.authService.logout();

      // Clear the authentication cookie
      res.clearCookie('token', {
        httpOnly: true,
        secure: process.env.NODE_ENV === 'production',
        sameSite: 'strict',
        path: '/',
      });

      // Redirect to login page
      return res.redirect('/login');
    } catch (error) {
      // Even if there's an error, redirect to login to ensure user is logged out
      return res.redirect('/login');
    }
  }

  @Get('protected')
  @UseGuards(JwtAuthGuard)
  async protectedRoute(@Req() req: Request, @Res() res: Response) {
    return res.json({
      message: 'This is a protected route',
      user: req.user,
    });
  }
}
