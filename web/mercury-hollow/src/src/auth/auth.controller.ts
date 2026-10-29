import {
  Controller,
  Post,
  Get,
  Body,
  UseGuards,
  Req,
  Res,
  HttpStatus,
  HttpCode,
  Render,
} from '@nestjs/common';
import type { Request, Response } from 'express';
import { AuthService } from './auth.service';
import { JwtAuthGuard } from './guards/jwt-auth.guard';
import { RolesGuard } from './guards/roles.guard';
import { Roles } from './decorators/roles.decorator';
import {
  LoginDto,
  TeamLoginDto,
  TeamRegisterDto,
  CreateSuperuserDto,
} from '../dto/auth.dto';
import { Permission } from '../entities/user.entity';

@Controller()
export class AuthController {
  constructor(private authService: AuthService) {}

  @Get('admin-login')
  @Render('admin-login')
  loginPage() {
    return {};
  }

  @Post('admin-login')
  async login(@Body() loginDto: LoginDto, @Res() res: Response) {
    try {
      const result = await this.authService.login(loginDto);

      // Set JWT token in cookie for authentication
      res.cookie('token', result.token, {
        httpOnly: true,
        secure: process.env.NODE_ENV === 'production',
        sameSite: 'strict',
        maxAge: 24 * 60 * 60 * 1000, // 24 hours
      });

      // Redirect to /secret route instead of rendering directly
      return res.redirect('/secret');
    } catch (error) {
      return res.render('admin-login', { error: error.message });
    }
  }

  @Get('register')
  @Render('register')
  teamRegisterPage() {
    return {};
  }

  @Post('register')
  async teamRegister(
    @Body() teamRegisterDto: TeamRegisterDto,
    @Res() res: Response,
  ) {
    try {
      await this.authService.teamRegister(teamRegisterDto);
      return res.redirect('/login');
    } catch (error) {
      return res.render('register', { error: error.message });
    }
  }

  @Get('login')
  @Render('login')
  teamLoginPage() {
    return {};
  }

  @Post('login')
  async teamLogin(@Body() teamLoginDto: TeamLoginDto, @Res() res: Response) {
    try {
      const result = await this.authService.teamLogin(teamLoginDto);

      // Set JWT token in cookie for authentication
      res.cookie('token', result.token, {
        httpOnly: true,
        secure: process.env.NODE_ENV === 'production',
        sameSite: 'strict',
        maxAge: 24 * 60 * 60 * 1000, // 24 hours
      });

      // Redirect to /secret route instead of rendering directly
      return res.redirect('/secret');
    } catch (error) {
      return res.render('login', { error: error.message });
    }
  }

  @Get('admin')
  @UseGuards(JwtAuthGuard, RolesGuard)
  @Roles(Permission.SUPERUSER)
  @Render('admin')
  async adminPage(@Req() req: Request) {
    const users = await this.authService.getAllUsers();
    const adminUsers = await this.authService.getAdminUsers();
    return { users, adminUsers };
  }

  @Post('admin/update-permission')
  @UseGuards(JwtAuthGuard, RolesGuard)
  @Roles(Permission.SUPERUSER)
  async updatePermission(
    @Body() body: { userId: number; permission: Permission },
    @Res() res: Response,
  ) {
    try {
      await this.authService.updateUserPermission(body.userId, {
        permission: body.permission,
      });
      return res.redirect('/admin');
    } catch (error) {
      return res.render('admin', { error: error.message });
    }
  }

  @Get('secret')
  @UseGuards(JwtAuthGuard)
  @Render('secret')
  async secretPage(@Req() req: Request) {
    const user = req.user as any;
    const flag =
      user.permission === Permission.ADMIN ||
      user.permission === Permission.SUPERUSER
        ? await this.authService.getFlag()
        : null;

    return {
      flag,
      user: {
        ...user,
        isSuperuser: user.permission === Permission.SUPERUSER,
      },
      token: req.cookies?.token || null,
    };
  }

  @Get('secret-guest')
  @Render('secret')
  secretGuestPage() {
    return {
      flag: null,
      user: { teamName: 'Guest', permission: 'user', isSuperuser: false },
    };
  }

  @Post('create-superuser')
  @HttpCode(HttpStatus.CREATED)
  async createSuperuser(
    @Body() createSuperuserDto: CreateSuperuserDto,
    @Res() res: Response,
  ) {
    try {
      const user = await this.authService.createSuperuser(createSuperuserDto);
      if (user) {
        return res
          .status(HttpStatus.CREATED)
          .json({ message: 'Superuser created successfully' });
      } else {
        return res
          .status(HttpStatus.NO_CONTENT)
          .json({ message: 'Superuser already exists' });
      }
    } catch (error) {
      return res.status(HttpStatus.BAD_REQUEST).json({ error: error.message });
    }
  }

  @Post('logout')
  @HttpCode(HttpStatus.OK)
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

  @Get('logout')
  async logoutGet(@Res() res: Response) {
    // Handle GET requests to logout (for direct URL access)
    return this.logout(res);
  }
}
