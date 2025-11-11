import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  UpdateDateColumn,
  ManyToOne,
  JoinColumn,
} from 'typeorm';
import { User } from './User.entity';

/**
 * Payment Retry Entity
 *
 * Tracks failed payment attempts and retry logic
 * Implements exponential backoff for transient failures
 * Dead Letter Queue (DLQ) for permanent failures
 */
@Entity('payment_retries')
export class PaymentRetry {
  @PrimaryGeneratedColumn()
  id: number;

  @Column()
  user_id: number;

  @ManyToOne(() => User)
  @JoinColumn({ name: 'user_id' })
  user: User;

  @Column('decimal', { precision: 18, scale: 8 })
  amount: string;

  @Column({
    type: 'enum',
    enum: ['REFERRAL_EARNING', 'DEPOSIT_REWARD'],
  })
  payment_type: 'REFERRAL_EARNING' | 'DEPOSIT_REWARD';

  @Column('simple-json')
  earning_ids: number[]; // Array of ReferralEarning or DepositReward IDs

  @Column({ default: 0 })
  attempt_count: number;

  @Column({ default: 5 })
  max_retries: number;

  @Column({ type: 'timestamp', nullable: true })
  last_attempt_at: Date | null;

  @Column({ type: 'timestamp', nullable: true })
  next_retry_at: Date | null;

  @Column({ type: 'text', nullable: true })
  last_error: string | null;

  @Column({ type: 'text', nullable: true })
  error_stack: string | null;

  @Column({ default: false })
  in_dlq: boolean; // Dead Letter Queue - max retries exceeded

  @Column({ default: false })
  resolved: boolean; // Successfully paid

  @Column({ type: 'varchar', length: 100, nullable: true })
  tx_hash: string | null; // Set when payment succeeds

  @CreateDateColumn()
  created_at: Date;

  @UpdateDateColumn()
  updated_at: Date;
}
