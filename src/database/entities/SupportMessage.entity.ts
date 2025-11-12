/**
 * Support Message Entity
 * Represents a message within a support ticket
 */

import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  ManyToOne,
  JoinColumn,
  Index,
} from 'typeorm';
import { SupportTicket } from './SupportTicket.entity';

export type SupportSender = 'user' | 'admin' | 'system';

@Entity('support_messages')
@Index(['ticket_id'])
export class SupportMessage {
  @PrimaryGeneratedColumn()
  id!: number;

  @Column({ type: 'int' })
  ticket_id!: number;

  @ManyToOne(() => SupportTicket)
  @JoinColumn({ name: 'ticket_id' })
  ticket!: SupportTicket;

  @Column({ type: 'varchar', length: 10 })
  sender!: SupportSender;

  @Column({ type: 'int', nullable: true })
  admin_id?: number;

  @Column({ type: 'text', nullable: true })
  text?: string;

  // Telegram attachments: [{type:'photo'|'voice'|'audio'|'document', file_id:'...'}]
  @Column({ type: 'jsonb', nullable: true })
  attachments?: Array<{ type: string; file_id: string; caption?: string }>;

  @CreateDateColumn()
  created_at!: Date;
}
