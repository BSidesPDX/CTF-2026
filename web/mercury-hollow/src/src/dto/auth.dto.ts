import { IsString, IsNotEmpty, IsOptional, IsEnum } from 'class-validator';
import { Permission } from '../entities/user.entity';

export class LoginDto {
  @IsString()
  @IsNotEmpty()
  teamName: string;

  @IsString()
  @IsNotEmpty()
  password: string;
}

export class TeamLoginDto {
  @IsString()
  @IsNotEmpty()
  teamName: string;
}

export class TeamRegisterDto {
  @IsString()
  @IsNotEmpty()
  teamName: string;
}

export class CreateSuperuserDto {
  @IsString()
  @IsNotEmpty()
  teamName: string;

  @IsString()
  @IsNotEmpty()
  password: string;
}

export class UpdatePermissionDto {
  @IsEnum(Permission)
  permission: Permission;
}

export class AuthResponseDto {
  teamName: string;
  permission: Permission;
  token?: string;
}
