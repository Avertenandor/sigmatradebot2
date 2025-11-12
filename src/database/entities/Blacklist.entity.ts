/**
 * Blacklist Entity
 * Represents users banned before registration (pre-registration ban)
 */

import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  Index,
} from 'typeorm';

@Entity('blacklist')
export class Blacklist {
  @PrimaryGeneratedColumn()
  id!: number;

  @Column({ type: 'bigint', unique: true })
  @Index()
  telegram_id!: number;

  @Column({ type: 'text', nullable: true })
  reason?: string;

  @Column({ type: 'integer', nullable: true })
  created_by_admin_id?: number;

  @CreateDateColumn()
  created_at!: Date;
}
