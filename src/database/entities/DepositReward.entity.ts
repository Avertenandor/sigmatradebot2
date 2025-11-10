/**
 * DepositReward Entity
 * Tracks rewards calculated and paid for deposits during reward sessions
 */

import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  UpdateDateColumn,
  ManyToOne,
  JoinColumn,
  Index,
  Unique,
} from 'typeorm';
import { Deposit } from './Deposit.entity';
import { RewardSession } from './RewardSession.entity';
import { User } from './User.entity';

@Entity('deposit_rewards')
@Unique(['deposit_id', 'reward_session_id']) // One reward per deposit per session
@Index(['user_id', 'paid']) // For querying user rewards
@Index(['reward_session_id', 'paid']) // For session statistics
export class DepositReward {
  @PrimaryGeneratedColumn()
  id!: number;

  @Column({ type: 'integer' })
  @Index()
  user_id!: number; // Denormalized for performance

  @ManyToOne(() => User)
  @JoinColumn({ name: 'user_id' })
  user!: User;

  @Column({ type: 'integer' })
  @Index()
  deposit_id!: number;

  @ManyToOne(() => Deposit)
  @JoinColumn({ name: 'deposit_id' })
  deposit!: Deposit;

  @Column({ type: 'integer' })
  @Index()
  reward_session_id!: number;

  @ManyToOne(() => RewardSession)
  @JoinColumn({ name: 'reward_session_id' })
  reward_session!: RewardSession;

  @Column({ type: 'integer' })
  deposit_level!: number; // Denormalized for reporting

  @Column({ type: 'decimal', precision: 20, scale: 8 })
  deposit_amount!: string; // Original deposit amount

  @Column({ type: 'decimal', precision: 10, scale: 4 })
  reward_rate!: string; // Applied reward rate (percentage)

  @Column({ type: 'decimal', precision: 20, scale: 8 })
  reward_amount!: string; // Calculated reward amount

  @Column({ type: 'boolean', default: false })
  @Index()
  paid!: boolean;

  @Column({ type: 'timestamp', nullable: true })
  paid_at?: Date;

  @Column({ type: 'varchar', length: 255, nullable: true })
  tx_hash?: string; // Transaction hash for reward payout

  @CreateDateColumn()
  calculated_at!: Date; // When reward was calculated

  @UpdateDateColumn()
  updated_at!: Date;

  // Virtual properties
  get displayRewardAmount(): string {
    return parseFloat(this.reward_amount).toFixed(2);
  }

  get displayDepositAmount(): string {
    return parseFloat(this.deposit_amount).toFixed(2);
  }

  get displayRewardRate(): string {
    return `${parseFloat(this.reward_rate).toFixed(4)}%`;
  }
}
