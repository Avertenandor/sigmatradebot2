/**
 * Wallet Change Request Entity
 * Represents a pending/approved/applied wallet change request
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
import { Admin } from './Admin.entity';

export type WalletChangeType = 'system_deposit' | 'payout_withdrawal';
export type WalletChangeStatus = 'pending' | 'approved' | 'applied' | 'rejected';

@Entity('wallet_change_requests')
@Index(['status'])
@Index(['type'])
@Index(['initiated_by_admin_id'])
export class WalletChangeRequest {
  @PrimaryGeneratedColumn()
  id!: number;

  @Column({ type: 'varchar', length: 50 })
  type!: WalletChangeType;

  @Column({ type: 'varchar', length: 42 })
  new_address!: string;

  @Column({ type: 'varchar', length: 255, nullable: true })
  secret_ref?: string;

  @Column({ type: 'int' })
  initiated_by_admin_id!: number;

  @ManyToOne(() => Admin)
  @JoinColumn({ name: 'initiated_by_admin_id' })
  initiated_by!: Admin;

  @Column({ type: 'int', nullable: true })
  approved_by_admin_id?: number;

  @ManyToOne(() => Admin, { nullable: true })
  @JoinColumn({ name: 'approved_by_admin_id' })
  approved_by?: Admin;

  @Column({ type: 'varchar', length: 20, default: 'pending' })
  status!: WalletChangeStatus;

  @Column({ type: 'text', nullable: true })
  reason?: string;

  @CreateDateColumn()
  created_at!: Date;

  @Column({ type: 'timestamp', nullable: true })
  approved_at?: Date;

  @Column({ type: 'timestamp', nullable: true })
  applied_at?: Date;

  // Virtual properties
  get isPending(): boolean {
    return this.status === 'pending';
  }

  get isApproved(): boolean {
    return this.status === 'approved';
  }

  get isApplied(): boolean {
    return this.status === 'applied';
  }

  get isRejected(): boolean {
    return this.status === 'rejected';
  }

  get isActive(): boolean {
    return this.status === 'pending' || this.status === 'approved';
  }

  get typeDisplay(): string {
    return this.type === 'system_deposit'
      ? 'System Deposit Wallet'
      : 'Payout Withdrawal Wallet';
  }

  get statusDisplay(): string {
    const statuses: Record<WalletChangeStatus, string> = {
      pending: '⏳ Pending',
      approved: '✅ Approved',
      applied: '🚀 Applied',
      rejected: '❌ Rejected',
    };
    return statuses[this.status];
  }
}
