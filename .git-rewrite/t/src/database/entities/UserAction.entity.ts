/**
 * UserAction Entity
 * Represents user actions for logging and analytics
 * TTL: 7 days (auto-deleted by cleanup job)
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

@Entity('user_actions')
export class UserAction {
  @PrimaryGeneratedColumn()
  id!: number;

  @Column({ type: 'integer', nullable: true })
  @Index()
  user_id?: number;

  @ManyToOne(() => User, { nullable: true })
  @JoinColumn({ name: 'user_id' })
  user?: User;

  @Column({ type: 'varchar', length: 50 })
  @Index()
  action_type!: string;

  @Column({ type: 'jsonb', nullable: true })
  details?: Record<string, any>;

  @Column({ type: 'inet', nullable: true })
  ip_address?: string;

  @CreateDateColumn()
  @Index()
  created_at!: Date;

  // Virtual property to check if action should be deleted
  get shouldBeDeleted(): boolean {
    const sevenDaysAgo = new Date();
    sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);
    return this.created_at < sevenDaysAgo;
  }
}
