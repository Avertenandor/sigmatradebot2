/**
 * Deposit Entity
 * Represents user deposits at different levels
 */

import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  Index,
  ManyToOne,
  JoinColumn,
  Check,
} from 'typeorm';
import { User } from './User.entity';
import { TransactionStatus } from '../../utils/constants';

@Entity('deposits')
@Check(`"level" >= 1 AND "level" <= 5`)
export class Deposit {
  @PrimaryGeneratedColumn()
  id!: number;

  @Column({ type: 'integer' })
  @Index()
  user_id!: number;

  @ManyToOne(() => User, (user) => user.deposits)
  @JoinColumn({ name: 'user_id' })
  user!: User;

  @Column({ type: 'integer' })
  @Index()
  level!: number; // 1-5

  @Column({ type: 'decimal', precision: 18, scale: 8 })
  amount!: string; // Stored as string to preserve precision

  @Column({ type: 'varchar', length: 66, unique: true })
  @Index()
  tx_hash!: string;

  @Column({
    type: 'varchar',
    length: 20,
    default: TransactionStatus.PENDING,
  })
  status!: string;

  @Column({ type: 'bigint', nullable: true })
  block_number?: number;

  @Column({ type: 'timestamp', nullable: true })
  confirmed_at?: Date;

  @CreateDateColumn()
  created_at!: Date;

  // Virtual property to get amount as number
  get amountAsNumber(): number {
    return parseFloat(this.amount);
  }

  // Check if deposit is confirmed
  get isConfirmed(): boolean {
    return this.status === TransactionStatus.CONFIRMED;
  }

  // Check if deposit is pending
  get isPending(): boolean {
    return this.status === TransactionStatus.PENDING;
  }

  // Check if deposit failed
  get isFailed(): boolean {
    return this.status === TransactionStatus.FAILED;
  }
}
