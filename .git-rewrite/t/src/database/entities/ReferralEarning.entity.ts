/**
 * ReferralEarning Entity
 * Represents individual referral earnings/payouts
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
import { Referral } from './Referral.entity';
import { Transaction } from './Transaction.entity';

@Entity('referral_earnings')
export class ReferralEarning {
  @PrimaryGeneratedColumn()
  id!: number;

  @Column({ type: 'integer' })
  @Index()
  referral_id!: number;

  @ManyToOne(() => Referral, (referral) => referral.earnings)
  @JoinColumn({ name: 'referral_id' })
  referral!: Referral;

  @Column({ type: 'decimal', precision: 18, scale: 8 })
  amount!: string;

  @Column({ type: 'integer', nullable: true })
  source_transaction_id?: number;

  @ManyToOne(() => Transaction, { nullable: true })
  @JoinColumn({ name: 'source_transaction_id' })
  source_transaction?: Transaction;

  @Column({ type: 'varchar', length: 66, nullable: true })
  tx_hash?: string; // Transaction hash of the payout

  @Column({ type: 'boolean', default: false })
  @Index()
  paid!: boolean;

  @CreateDateColumn()
  created_at!: Date;

  // Virtual properties
  get amountAsNumber(): number {
    return parseFloat(this.amount);
  }

  get isPaid(): boolean {
    return this.paid;
  }

  get isPending(): boolean {
    return !this.paid;
  }
}
