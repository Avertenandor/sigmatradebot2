/**
 * Admin Entity
 * Represents administrators with elevated privileges
 */

import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  Index,
  ManyToOne,
  JoinColumn,
} from 'typeorm';

@Entity('admins')
export class Admin {
  @PrimaryGeneratedColumn()
  id!: number;

  @Column({ type: 'bigint', unique: true })
  @Index()
  telegram_id!: number;

  @Column({ type: 'varchar', length: 255, nullable: true })
  username?: string;

  @Column({ type: 'varchar', length: 20, default: 'admin' })
  role!: string; // admin, super_admin

  @Column({ type: 'integer', nullable: true })
  created_by?: number;

  @ManyToOne(() => Admin, { nullable: true })
  @JoinColumn({ name: 'created_by' })
  creator?: Admin;

  @CreateDateColumn()
  created_at!: Date;

  // Virtual properties
  get isSuperAdmin(): boolean {
    return this.role === 'super_admin';
  }

  get isAdmin(): boolean {
    return this.role === 'admin' || this.role === 'super_admin';
  }

  get displayName(): string {
    return this.username || `Admin${this.telegram_id}`;
  }
}
