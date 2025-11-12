/**
 * SystemSetting Entity
 * Runtime configuration settings that can be changed by admins
 *
 * Settings stored:
 * - DEPOSITS_MAX_OPEN_LEVEL: Maximum deposit level open to users (1-5)
 *
 * Cached in memory with TTL for performance (60s)
 * Use SettingsService to access/modify settings
 */

import { Entity, PrimaryColumn, Column, UpdateDateColumn } from 'typeorm';

@Entity('system_settings')
export class SystemSetting {
  @PrimaryColumn({ type: 'varchar', length: 100 })
  key!: string;

  @Column({ type: 'text' })
  value!: string;

  @UpdateDateColumn()
  updated_at!: Date;
}
