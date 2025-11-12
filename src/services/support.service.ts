/**
 * Support Service
 * Business logic for support ticket system
 */

import { AppDataSource } from '../database';
import { SupportTicket, SupportMessage } from '../database/entities';
import { MoreThan } from 'typeorm';
import type { SupportCategory, SupportStatus, SupportSender } from '../database/entities/SupportTicket.entity';
import { AdminSession } from '../database/entities/AdminSession.entity';

export interface CreateTicketData {
  userId: number;
  category: SupportCategory;
  initialMessage?: string;
  attachments?: Array<{ type: string; file_id: string; caption?: string }>;
}

export interface AddMessageData {
  ticketId: number;
  sender: SupportSender;
  adminId?: number;
  text?: string;
  attachments?: Array<{ type: string; file_id: string; caption?: string }>;
}

export class SupportService {
  private ticketRepo = AppDataSource.getRepository(SupportTicket);
  private messageRepo = AppDataSource.getRepository(SupportMessage);
  private adminSessionRepo = AppDataSource.getRepository(AdminSession);

  /**
   * Create a new support ticket
   */
  async createTicket(data: CreateTicketData): Promise<SupportTicket> {
    // Check if user already has an open ticket
    const existingOpen = await this.ticketRepo.findOne({
      where: {
        user_id: data.userId,
        status: 'open' as SupportStatus,
      },
    });

    if (existingOpen) {
      throw new Error('У вас уже есть открытое обращение. Пожалуйста, дождитесь ответа администратора.');
    }

    // Check in_progress and answered as well (partial UNIQUE index covers these)
    const existingActive = await this.ticketRepo
      .createQueryBuilder('ticket')
      .where('ticket.user_id = :userId', { userId: data.userId })
      .andWhere('ticket.status IN (:...statuses)', { statuses: ['open', 'in_progress', 'answered'] })
      .getOne();

    if (existingActive) {
      throw new Error('У вас уже есть активное обращение. Пожалуйста, дождитесь его закрытия.');
    }

    // Create ticket
    const ticket = this.ticketRepo.create({
      user_id: data.userId,
      category: data.category,
      status: 'open',
      last_user_message_at: new Date(),
    });

    await this.ticketRepo.save(ticket);

    // Add initial message if provided
    if (data.initialMessage || data.attachments) {
      await this.addUserMessage({
        ticketId: ticket.id,
        sender: 'user',
        text: data.initialMessage,
        attachments: data.attachments,
      });
    }

    return ticket;
  }

  /**
   * Add user message to ticket
   */
  async addUserMessage(data: AddMessageData): Promise<SupportMessage> {
    const message = this.messageRepo.create({
      ticket_id: data.ticketId,
      sender: 'user',
      text: data.text,
      attachments: data.attachments,
    });

    await this.messageRepo.save(message);

    // Update ticket last_user_message_at
    await this.ticketRepo.update(data.ticketId, {
      last_user_message_at: new Date(),
      status: 'open', // Reset to open when user sends new message
    });

    return message;
  }

  /**
   * Add admin message to ticket
   */
  async addAdminMessage(data: AddMessageData): Promise<SupportMessage> {
    if (!data.adminId) {
      throw new Error('Admin ID required for admin messages');
    }

    const message = this.messageRepo.create({
      ticket_id: data.ticketId,
      sender: 'admin',
      admin_id: data.adminId,
      text: data.text,
      attachments: data.attachments,
    });

    await this.messageRepo.save(message);

    // Update ticket last_admin_message_at and status
    await this.ticketRepo.update(data.ticketId, {
      last_admin_message_at: new Date(),
      status: 'answered', // Mark as answered when admin replies
    });

    return message;
  }

  /**
   * Add system message to ticket
   */
  async addSystemMessage(ticketId: number, text: string): Promise<SupportMessage> {
    const message = this.messageRepo.create({
      ticket_id: ticketId,
      sender: 'system',
      text,
    });

    await this.messageRepo.save(message);
    return message;
  }

  /**
   * Assign ticket to admin
   */
  async assignToSelf(ticketId: number, adminId: number): Promise<void> {
    await this.ticketRepo.update(ticketId, {
      assigned_admin_id: adminId,
      status: 'in_progress',
    });
  }

  /**
   * Close ticket
   */
  async close(ticketId: number): Promise<void> {
    await this.ticketRepo.update(ticketId, {
      status: 'closed',
    });
  }

  /**
   * Reopen closed ticket
   */
  async reopen(ticketId: number): Promise<void> {
    await this.ticketRepo.update(ticketId, {
      status: 'open',
    });
  }

  /**
   * List open tickets for admin
   */
  async listOpen(): Promise<SupportTicket[]> {
    return this.ticketRepo.find({
      where: [
        { status: 'open' },
        { status: 'in_progress' },
        { status: 'answered' },
      ],
      relations: ['user', 'assigned_admin'],
      order: {
        created_at: 'DESC',
      },
    });
  }

  /**
   * Get ticket by ID with messages
   */
  async get(ticketId: number): Promise<SupportTicket | null> {
    return this.ticketRepo.findOne({
      where: { id: ticketId },
      relations: ['user', 'assigned_admin', 'messages'],
      order: {
        messages: {
          created_at: 'ASC',
        },
      },
    });
  }

  /**
   * Get user's active ticket (open, in_progress, or answered)
   */
  async getUserActiveTicket(userId: number): Promise<SupportTicket | null> {
    return this.ticketRepo
      .createQueryBuilder('ticket')
      .where('ticket.user_id = :userId', { userId })
      .andWhere('ticket.status IN (:...statuses)', { statuses: ['open', 'in_progress', 'answered'] })
      .leftJoinAndSelect('ticket.messages', 'messages')
      .orderBy('messages.created_at', 'ASC')
      .getOne();
  }

  /**
   * Find on-duty admin (admin with active session)
   */
  async findOnDutyAdmin(): Promise<number | null> {
    const now = new Date();

    // Find active admin session
    const activeSession = await this.adminSessionRepo.findOne({
      where: {
        is_active: true,
        expires_at: MoreThan(now),
      },
      order: {
        last_activity: 'DESC',
      },
    });

    return activeSession?.admin_id || null;
  }
}

export const supportService = new SupportService();
