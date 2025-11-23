/**
 * User Entity
 * Represents registered users in the system
 */

import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  UpdateDateColumn,
  Index,
  OneToMany,
  ManyToOne,
  JoinColumn,
} from 'typeorm';
import { Deposit } from './Deposit.entity';
import { Transaction } from './Transaction.entity';
import { Referral } from './Referral.entity';

@Entity('users')
export class User {
  @PrimaryGeneratedColumn()
  id!: number;

  @Column({ type: 'bigint', unique: true })
  @Index()
  telegram_id!: number;

  @Column({ type: 'varchar', length: 255, nullable: true })
  username?: string;

  @Column({ type: 'varchar', length: 42, unique: true })
  @Index()
  wallet_address!: string;

  @Column({ type: 'varchar', length: 255 })
  financial_password!: string; // bcrypt hashed

  @Column({ type: 'varchar', length: 20, nullable: true })
  phone?: string;

  @Column({ type: 'varchar', length: 255, nullable: true })
  email?: string;

  @Column({ type: 'integer', nullable: true })
  @Index()
  referrer_id?: number;

  @ManyToOne(() => User, { nullable: true })
  @JoinColumn({ name: 'referrer_id' })
  referrer?: User;

  @Column({ type: 'boolean', default: false })
  is_verified!: boolean;

  @Column({ type: 'boolean', default: false })
  is_banned!: boolean;

  @CreateDateColumn()
  created_at!: Date;

  @UpdateDateColumn()
  updated_at!: Date;

  // Relations
  @OneToMany(() => Deposit, (deposit) => deposit.user)
  deposits!: Deposit[];

  @OneToMany(() => Transaction, (transaction) => transaction.user)
  transactions!: Transaction[];

  @OneToMany(() => Referral, (referral) => referral.referrer)
  referrals_as_referrer!: Referral[];

  @OneToMany(() => Referral, (referral) => referral.referral_user)
  referrals_as_referral!: Referral[];

  // Virtual properties
  get maskedWallet(): string {
    if (!this.wallet_address || this.wallet_address.length < 10) {
      return this.wallet_address;
    }
    const start = this.wallet_address.substring(0, 6);
    const end = this.wallet_address.substring(this.wallet_address.length - 4);
    return `${start}...${end}`;
  }

  get displayName(): string {
    return this.username || `User${this.telegram_id}`;
  }
}
