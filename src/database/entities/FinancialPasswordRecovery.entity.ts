/**
 * Financial Password Recovery Entity
 * Manages user requests to reset their financial password (3-5 business days SLA)
 *
 * Process:
 * 1. User creates request → status: 'pending', all admins notified
 * 2. Admin reviews → status: 'in_review'
 * 3. Admin approves → new password generated, hashed, sent to user → status: 'sent'
 * 4. OR admin rejects → status: 'rejected'
 *
 * Anti-abuse: Unique constraint prevents multiple open requests per user
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
import { User } from './User.entity';
import { Admin } from './Admin.entity';

export type FinpassRecoveryStatus = 'pending' | 'in_review' | 'approved' | 'rejected' | 'sent';

@Entity('financial_password_recovery')
export class FinancialPasswordRecovery {
  @PrimaryGeneratedColumn()
  id!: number;

  @Column({ type: 'int' })
  @Index()
  user_id!: number;

  @ManyToOne(() => User)
  @JoinColumn({ name: 'user_id' })
  user?: User;

  @Column({ type: 'varchar', length: 20, default: 'pending' })
  @Index()
  status!: FinpassRecoveryStatus;

  @Column({ type: 'boolean', default: true })
  video_required!: boolean;

  @Column({ type: 'boolean', default: false })
  video_verified!: boolean;

  @Column({ type: 'int', nullable: true })
  processed_by_admin_id?: number;

  @ManyToOne(() => Admin, { nullable: true })
  @JoinColumn({ name: 'processed_by_admin_id' })
  processed_by_admin?: Admin;

  @Column({ type: 'timestamp', nullable: true })
  processed_at?: Date;

  @Column({ type: 'text', nullable: true })
  admin_comment?: string;

  @CreateDateColumn()
  created_at!: Date;

  @UpdateDateColumn()
  updated_at!: Date;
}
