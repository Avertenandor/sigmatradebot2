/**
 * Deposit Entity
 * Represents user deposits at different levels
 */

import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  Index,
  ManyToOne,
  JoinColumn,
  Check,
} from 'typeorm';
import { User } from './User.entity';
import { TransactionStatus } from '../../utils/constants';

@Entity('deposits')
@Check(`"level" >= 1 AND "level" <= 5`)
@Index(['user_id', 'status']) // Compound index for user deposit queries
@Index(['user_id', 'level', 'status']) // Compound index for level-specific deposit queries
@Index(['status', 'created_at']) // Compound index for pending deposit cleanup
export class Deposit {
  @PrimaryGeneratedColumn()
  id!: number;

  @Column({ type: 'integer' })
  @Index()
  user_id!: number;

  @ManyToOne(() => User, (user) => user.deposits)
  @JoinColumn({ name: 'user_id' })
  user!: User;

  @Column({ type: 'integer' })
  @Index()
  level!: number; // 1-5

  @Column({ type: 'decimal', precision: 18, scale: 8 })
  amount!: string; // Stored as string to preserve precision

  @Column({ type: 'varchar', length: 66, nullable: true })
  @Index()
  tx_hash?: string;

  @Column({
    type: 'varchar',
    length: 20,
    default: TransactionStatus.PENDING,
  })
  status!: string;

  @Column({ type: 'bigint', nullable: true })
  block_number?: number;

  @Column({ type: 'timestamp', nullable: true })
  confirmed_at?: Date;

  // ROI (Return on Investment) tracking for Level 1 deposits
  // Level 1 has 500% ROI cap: maximum earnings = 5x deposit amount
  @Column({ type: 'decimal', precision: 20, scale: 8, nullable: true })
  roi_cap_amount?: string; // Maximum total earnings allowed (5x amount for L1)

  @Column({ type: 'decimal', precision: 20, scale: 8, default: '0' })
  roi_paid_amount!: string; // Total earnings paid out so far

  @Column({ type: 'boolean', default: false })
  @Index()
  is_roi_completed!: boolean; // Flag: ROI cap reached, cycle completed

  @Column({ type: 'timestamp', nullable: true })
  roi_completed_at?: Date; // When ROI cap was reached

  @CreateDateColumn()
  created_at!: Date;

  // Virtual property to get amount as number
  get amountAsNumber(): number {
    return parseFloat(this.amount);
  }

  // Get ROI progress percentage (0-100)
  get roiProgressPercent(): number {
    const cap = parseFloat(this.roi_cap_amount || '0');
    const paid = parseFloat(this.roi_paid_amount || '0');
    if (cap === 0) return 0;
    return Math.min((paid / cap) * 100, 100);
  }

  // Get remaining ROI amount before cap
  get roiRemainingAmount(): number {
    const cap = parseFloat(this.roi_cap_amount || '0');
    const paid = parseFloat(this.roi_paid_amount || '0');
    if (cap === 0) return Infinity;
    return Math.max(cap - paid, 0);
  }

  // Check if deposit is confirmed
  get isConfirmed(): boolean {
    return this.status === TransactionStatus.CONFIRMED;
  }

  // Check if deposit is pending
  get isPending(): boolean {
    return this.status === TransactionStatus.PENDING;
  }

  // Check if deposit failed
  get isFailed(): boolean {
    return this.status === TransactionStatus.FAILED;
  }
}
