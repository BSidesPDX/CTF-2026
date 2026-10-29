import { SetMetadata } from '@nestjs/common';
import { Permission } from '../../entities/user.entity';

export const Roles = (...roles: Permission[]) => SetMetadata('roles', roles);
