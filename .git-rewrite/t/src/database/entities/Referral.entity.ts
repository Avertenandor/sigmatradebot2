/**
 * Referral Entity
 * Represents referral relationships between users
 */

import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  Index,
  ManyToOne,
  JoinColumn,
  OneToMany,
  Check,
  Unique,
} from 'typeorm';
import { User } from './User.entity';
import { ReferralEarning } from './ReferralEarning.entity';

@Entity('referrals')
@Unique(['referrer_id', 'referral_id'])
@Check(`"level" >= 1 AND "level" <= 3`)
export class Referral {
  @PrimaryGeneratedColumn()
  id!: number;

  @Column({ type: 'integer' })
  @Index()
  referrer_id!: number;

  @ManyToOne(() => User, (user) => user.referrals_as_referrer)
  @JoinColumn({ name: 'referrer_id' })
  referrer!: User;

  @Column({ type: 'integer' })
  @Index()
  referral_id!: number;

  @ManyToOne(() => User, (user) => user.referrals_as_referral)
  @JoinColumn({ name: 'referral_id' })
  referral_user!: User;

  @Column({ type: 'integer' })
  level!: number; // 1-3 (referral depth)

  @Column({ type: 'decimal', precision: 18, scale: 8, default: 0 })
  total_earned!: string;

  @CreateDateColumn()
  created_at!: Date;

  // Relations
  @OneToMany(() => ReferralEarning, (earning) => earning.referral)
  earnings!: ReferralEarning[];

  // Virtual properties
  get totalEarnedAsNumber(): number {
    return parseFloat(this.total_earned);
  }
}
