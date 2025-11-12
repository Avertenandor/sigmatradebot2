/**
 * Financial Password Recovery Entity
 * Manages user requests to reset their financial password (3-5 business days SLA)
 *
 * Process:
 * 1. User creates request → status: 'pending', EARNINGS BLOCKED, all admins notified
 * 2. Admin conducts video verification OUTSIDE bot (Telegram DM, WhatsApp, etc)
 * 3. Admin reviews → status: 'in_review'
 * 4. Admin approves → new password generated, hashed, sent to user → status: 'sent'
 * 5. User successfully uses new password → EARNINGS UNBLOCKED
 * 6. OR admin rejects → status: 'rejected', earnings remain blocked
 *
 * CRITICAL Security:
 * - User earnings blocked from request creation until first successful password use
 * - Prevents unauthorized withdrawals during recovery period
 *
 * Anti-abuse: Unique constraint prevents multiple open requests per user
 *
 * Video Verification:
 * - Conducted OUTSIDE bot via external channels (Telegram DM, WhatsApp, etc)
 * - Bot does NOT handle video upload/storage
 * - Fields video_required/video_verified are admin markers only
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

  // Video verification conducted OUTSIDE bot (Telegram DM, WhatsApp, email, etc)
  // Bot does NOT handle video upload/storage - these are admin markers only
  @Column({ type: 'boolean', default: true })
  video_required!: boolean; // Admin marker: is video verification needed?

  @Column({ type: 'boolean', default: false })
  video_verified!: boolean; // Admin marker: was video verified externally?

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
