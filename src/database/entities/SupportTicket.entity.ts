/**
 * Support Ticket Entity
 * Represents a support ticket created by a user
 */

import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  UpdateDateColumn,
  Index,
  ManyToOne,
  JoinColumn,
  OneToMany,
} from 'typeorm';
import { User } from './User.entity';
import { Admin } from './Admin.entity';
import { SupportMessage } from './SupportMessage.entity';

export type SupportStatus = 'open' | 'in_progress' | 'answered' | 'closed';
export type SupportCategory = 'payments' | 'withdrawals' | 'finpass' | 'referrals' | 'tech' | 'other';

@Entity('support_tickets')
@Index(['user_id'])
@Index(['status'])
@Index(['assigned_admin_id'])
export class SupportTicket {
  @PrimaryGeneratedColumn()
  id!: number;

  @Column({ type: 'int' })
  user_id!: number;

  @ManyToOne(() => User)
  @JoinColumn({ name: 'user_id' })
  user!: User;

  @Column({ type: 'varchar', length: 20 })
  category!: SupportCategory;

  @Column({ type: 'varchar', length: 20, default: 'open' })
  status!: SupportStatus;

  @Column({ type: 'int', nullable: true })
  assigned_admin_id?: number;

  @ManyToOne(() => Admin, { nullable: true })
  @JoinColumn({ name: 'assigned_admin_id' })
  assigned_admin?: Admin;

  @Column({ type: 'timestamp', nullable: true })
  last_user_message_at?: Date;

  @Column({ type: 'timestamp', nullable: true })
  last_admin_message_at?: Date;

  @CreateDateColumn()
  created_at!: Date;

  @UpdateDateColumn()
  updated_at!: Date;

  @OneToMany(() => SupportMessage, (m) => m.ticket)
  messages!: SupportMessage[];
}
