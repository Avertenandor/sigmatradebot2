/**
 * RewardSession Entity
 * Defines reward calculation sessions with time periods and rates per deposit level
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
} from 'typeorm';
import { Admin } from './Admin.entity';

@Entity('reward_sessions')
export class RewardSession {
  @PrimaryGeneratedColumn()
  id!: number;

  @Column({ type: 'varchar', length: 255 })
  name!: string; // Session name (e.g., "July 2024 Promo")

  // Reward rates for each deposit level (percentage)
  @Column({ type: 'decimal', precision: 10, scale: 4 })
  reward_rate_level_1!: string; // e.g., "1.1170" for 1.117%

  @Column({ type: 'decimal', precision: 10, scale: 4 })
  reward_rate_level_2!: string;

  @Column({ type: 'decimal', precision: 10, scale: 4 })
  reward_rate_level_3!: string;

  @Column({ type: 'decimal', precision: 10, scale: 4 })
  reward_rate_level_4!: string;

  @Column({ type: 'decimal', precision: 10, scale: 4 })
  reward_rate_level_5!: string;

  @Column({ type: 'timestamp' })
  @Index()
  start_date!: Date; // Rewards calculated for deposits confirmed after this date

  @Column({ type: 'timestamp' })
  @Index()
  end_date!: Date; // Rewards calculated for deposits confirmed before this date

  @Column({ type: 'boolean', default: true })
  @Index()
  is_active!: boolean; // Only active sessions are processed

  @Column({ type: 'integer', nullable: true })
  created_by?: number; // Admin who created the session

  @ManyToOne(() => Admin, { nullable: true })
  @JoinColumn({ name: 'created_by' })
  creator?: Admin;

  @CreateDateColumn()
  created_at!: Date;

  @UpdateDateColumn()
  updated_at!: Date;

  // Virtual properties
  get isCurrentlyActive(): boolean {
    if (!this.is_active) return false;

    const now = new Date();
    return now >= this.start_date && now <= this.end_date;
  }

  get remainingDays(): number {
    const now = Date.now();
    const endTime = this.end_date.getTime();

    if (endTime < now) return 0;

    return Math.ceil((endTime - now) / (1000 * 60 * 60 * 24));
  }

  /**
   * Get reward rate for specific deposit level
   */
  getRewardRateForLevel(level: number): number {
    switch (level) {
      case 1:
        return parseFloat(this.reward_rate_level_1);
      case 2:
        return parseFloat(this.reward_rate_level_2);
      case 3:
        return parseFloat(this.reward_rate_level_3);
      case 4:
        return parseFloat(this.reward_rate_level_4);
      case 5:
        return parseFloat(this.reward_rate_level_5);
      default:
        return 0;
    }
  }
}
