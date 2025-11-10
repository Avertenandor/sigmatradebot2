/**
 * AdminSession Entity
 * Tracks active admin sessions with 1-hour inactivity timeout
 */

import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  UpdateDateColumn,
  Index,
  ManyToOne,
  JoinColumn,
} from 'typeorm';
import { Admin } from './Admin.entity';

@Entity('admin_sessions')
@Index(['admin_id', 'is_active']) // Compound index for active session queries
@Index(['last_activity']) // Index for cleanup queries
export class AdminSession {
  @PrimaryGeneratedColumn()
  id!: number;

  @Column({ type: 'integer' })
  @Index()
  admin_id!: number;

  @ManyToOne(() => Admin)
  @JoinColumn({ name: 'admin_id' })
  admin!: Admin;

  @Column({ type: 'varchar', length: 255, unique: true })
  @Index()
  session_token!: string; // Unique session identifier

  @Column({ type: 'boolean', default: true })
  is_active!: boolean;

  @Column({ type: 'varchar', length: 255, nullable: true })
  ip_address?: string; // For security logging

  @Column({ type: 'varchar', length: 255, nullable: true })
  user_agent?: string; // For security logging

  @CreateDateColumn()
  created_at!: Date;

  @UpdateDateColumn()
  last_activity!: Date; // Updated on each action

  @Column({ type: 'timestamp', nullable: true })
  expires_at?: Date; // 1 hour from last_activity

  // Virtual properties
  get isExpired(): boolean {
    if (!this.expires_at) return false;
    return new Date() > this.expires_at;
  }

  get remainingTimeMinutes(): number {
    if (!this.expires_at) return 0;
    const remaining = this.expires_at.getTime() - Date.now();
    return Math.max(0, Math.floor(remaining / 1000 / 60));
  }

  /**
   * Update last activity and extend expiration
   */
  updateActivity(): void {
    this.last_activity = new Date();
    this.expires_at = new Date(Date.now() + 60 * 60 * 1000); // 1 hour from now
  }
}
