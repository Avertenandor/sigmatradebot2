/**
 * Transaction Entity
 * Represents all blockchain transactions (deposits, payouts, rewards)
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
import { User } from './User.entity';
import { TransactionStatus, TransactionType } from '../../utils/constants';

@Entity('transactions')
export class Transaction {
  @PrimaryGeneratedColumn()
  id!: number;

  @Column({ type: 'integer', nullable: true })
  @Index()
  user_id?: number;

  @ManyToOne(() => User, (user) => user.transactions, { nullable: true })
  @JoinColumn({ name: 'user_id' })
  user?: User;

  @Column({ type: 'varchar', length: 66, unique: true })
  @Index()
  tx_hash!: string;

  @Column({ type: 'varchar', length: 20 })
  @Index()
  type!: string; // deposit, referral_reward, system_payout

  @Column({ type: 'decimal', precision: 18, scale: 8 })
  amount!: string;

  @Column({ type: 'varchar', length: 42, nullable: true })
  from_address?: string;

  @Column({ type: 'varchar', length: 42, nullable: true })
  to_address?: string;

  @Column({ type: 'bigint', nullable: true })
  block_number?: number;

  @Column({
    type: 'varchar',
    length: 20,
    default: TransactionStatus.PENDING,
  })
  status!: string;

  @CreateDateColumn()
  created_at!: Date;

  // Virtual properties
  get amountAsNumber(): number {
    return parseFloat(this.amount);
  }

  get isConfirmed(): boolean {
    return this.status === TransactionStatus.CONFIRMED;
  }

  get isPending(): boolean {
    return this.status === TransactionStatus.PENDING;
  }

  get isFailed(): boolean {
    return this.status === TransactionStatus.FAILED;
  }

  get isDeposit(): boolean {
    return this.type === TransactionType.DEPOSIT;
  }

  get isReferralReward(): boolean {
    return this.type === TransactionType.REFERRAL_REWARD;
  }

  get isSystemPayout(): boolean {
    return this.type === TransactionType.SYSTEM_PAYOUT;
  }

  // BSCScan link
  get explorerLink(): string {
    return `https://bscscan.com/tx/${this.tx_hash}`;
  }
}
