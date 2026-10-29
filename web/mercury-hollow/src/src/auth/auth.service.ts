import {
  Injectable,
  UnauthorizedException,
  ConflictException,
  NotFoundException,
} from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { JwtService } from '@nestjs/jwt';
import * as bcrypt from 'bcryptjs';
import { User, Permission } from '../entities/user.entity';
import {
  LoginDto,
  TeamLoginDto,
  TeamRegisterDto,
  CreateSuperuserDto,
  UpdatePermissionDto,
} from '../dto/auth.dto';

@Injectable()
export class AuthService {
  constructor(
    @InjectRepository(User)
    private userRepository: Repository<User>,
    private jwtService: JwtService,
  ) {}

  async validateUser(teamName: string, password: string): Promise<User | null> {
    const user = await this.userRepository.findOne({ where: { teamName } });
    if (
      user &&
      user.password &&
      (await bcrypt.compare(password, user.password))
    ) {
      return user;
    }
    return null;
  }

  async validateTeam(teamName: string): Promise<User | null> {
    const user = await this.userRepository.findOne({ where: { teamName } });
    return user;
  }

  async login(loginDto: LoginDto): Promise<{ user: User; token: string }> {
    const user = await this.validateUser(loginDto.teamName, loginDto.password);
    if (!user) {
      throw new UnauthorizedException('Invalid credentials');
    }

    const payload = {
      teamName: user.teamName,
      sub: user.id,
      permission: user.permission,
    };
    const token = this.jwtService.sign(payload);

    return { user, token };
  }

  async teamLogin(
    teamLoginDto: TeamLoginDto,
  ): Promise<{ user: User; token: string }> {
    const user = await this.validateTeam(teamLoginDto.teamName);
    if (!user) {
      throw new UnauthorizedException('Team not found');
    }

    const payload = {
      teamName: user.teamName,
      sub: user.id,
      permission: user.permission,
    };
    const token = this.jwtService.sign(payload);

    return { user, token };
  }

  async teamRegister(teamRegisterDto: TeamRegisterDto): Promise<User> {
    const existingUser = await this.userRepository.findOne({
      where: { teamName: teamRegisterDto.teamName },
    });
    if (existingUser) {
      throw new ConflictException('Team name already exists');
    }

    const user = this.userRepository.create({
      teamName: teamRegisterDto.teamName,
      permission: Permission.USER,
    });

    return await this.userRepository.save(user);
  }

  async createSuperuser(
    createSuperuserDto: CreateSuperuserDto,
  ): Promise<User | null> {
    // Check if superuser already exists
    const existingSuperuser = await this.userRepository.findOne({
      where: { permission: Permission.SUPERUSER },
    });

    if (existingSuperuser) {
      return null; // Return null to indicate superuser already exists
    }

    const hashedPassword = await bcrypt.hash(createSuperuserDto.password, 10);

    const user = this.userRepository.create({
      teamName: createSuperuserDto.teamName,
      password: hashedPassword,
      permission: Permission.SUPERUSER,
    });

    return await this.userRepository.save(user);
  }

  async getAllUsers(): Promise<User[]> {
    return await this.userRepository.find({
      where: { permission: Permission.USER },
      order: { createdAt: 'ASC' },
    });
  }

  async getAdminUsers(): Promise<User[]> {
    return await this.userRepository.find({
      where: { permission: Permission.ADMIN },
      order: { createdAt: 'ASC' },
    });
  }

  async updateUserPermission(
    userId: number,
    updatePermissionDto: UpdatePermissionDto,
  ): Promise<User> {
    const user = await this.userRepository.findOne({ where: { id: userId } });
    if (!user) {
      throw new NotFoundException('User not found');
    }

    // Prevent changing superuser permission
    if (user.permission === Permission.SUPERUSER) {
      throw new ConflictException('Cannot modify superuser permissions');
    }

    user.permission = updatePermissionDto.permission;
    return await this.userRepository.save(user);
  }

  async getFlag(): Promise<string> {
    return `pdx{HaveYouEverBeenSoFarAsToSee}`;
  }

  async logout(): Promise<{ message: string }> {
    return { message: 'Logged out successfully' };
  }
}
