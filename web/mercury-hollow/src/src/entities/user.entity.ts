import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  UpdateDateColumn,
} from 'typeorm';

export enum Permission {
  USER = 'user',
  ADMIN = 'admin',
  SUPERUSER = 'superuser',
}

@Entity('users')
export class User {
  @PrimaryGeneratedColumn()
  id: number;

  @Column({ unique: true })
  teamName: string;

  @Column({
    type: 'enum',
    enum: Permission,
    default: Permission.USER,
  })
  permission: Permission;

  @Column({ nullable: true })
  password?: string;

  @CreateDateColumn()
  createdAt: Date;

  @UpdateDateColumn()
  updatedAt: Date;
}
