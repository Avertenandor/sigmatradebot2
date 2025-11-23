/**
 * Telegram Bot Main Module
 * Initializes and configures the Telegraf bot instance
 */

import { Telegraf } from 'telegraf';
import { config } from '../config';
import { createLogger } from '../utils/logger.util';
import { notificationService } from '../services/notification.service';

// Middlewares
import {
  loggerMiddleware,
  sessionMiddleware,
  authMiddleware,
  banMiddleware,
  adminMiddleware,
  rateLimitMiddleware,
  registrationRateLimitMiddleware,
} from './middlewares';

// Handlers
import {
  handleStart,
  handleMainMenu,
  handleHelp,
  handleStartRegistration,
  handleWalletInput,
  handleStartVerification,
  handleAddContactInfo,
  handleContactInfoInput,
  handleSkipContactInfo,
  handleCancelRegistration,
  handleProfile,
  handleDeposits,
  handleDepositLevel,
  handleActivateDeposit,
  handleCheckPendingDeposits,
  handleDepositHistory,
  handleCancelDeposit,
  handleWithdrawals,
  handleRequestWithdrawal,
  handleWithdrawalAmountInput,
  handleWithdrawalPasswordInput,
  handleWithdrawalHistory,
  handleTransactionHistory,
  handleTransactionHistoryFilter,
  handleReferrals,
  handleReferralLink,
  handleReferralStats,
  handleReferralEarnings,
  handleReferralLeaderboard,
  handleAdminPanel,
  handleAdminStats,
  handleStartBroadcast,
  handleBroadcastMessage,
  handleStartSendToUser,
  handleSendToUserMessage,
  handleStartBanUser,
  handleBanUserInput,
  handleStartUnbanUser,
  handleUnbanUserInput,
  handleStartPromoteAdmin,
  handlePromoteAdminInput,
  handlePendingWithdrawals,
  handleApproveWithdrawal,
  handleRejectWithdrawal,
} from './handlers';

// Context types
import { AuthContext } from './middlewares/auth.middleware';
import { SessionContext } from './middlewares/session.middleware';
import { AdminContext } from './middlewares/admin.middleware';
import { BotState } from '../utils/constants';

const logger = createLogger('TelegramBot');

// Extended context type
export type BotContext = AuthContext & SessionContext & AdminContext;

/**
 * Initialize Telegram bot
 */
export const initializeBot = (): Telegraf => {
  const bot = new Telegraf(config.telegram.botToken);

  // Initialize notification service with bot instance
  notificationService.setBot(bot);

  // Apply global middlewares
  bot.use(loggerMiddleware);
  bot.use(rateLimitMiddleware);
  bot.use(sessionMiddleware);
  bot.use(authMiddleware);
  bot.use(banMiddleware);
  bot.use(adminMiddleware);

  // ==================== COMMANDS ====================

  /**
   * /start command
   * Entry point for all users
   */
  bot.command('start', handleStart);

  /**
   * /help command
   */
  bot.command('help', handleHelp);

  // ==================== CALLBACK QUERIES ====================

  /**
   * Main menu
   */
  bot.action('main_menu', handleMainMenu);

  /**
   * Help
   */
  bot.action('help', handleHelp);

  /**
   * Registration flow
   */
  bot.action('start_registration', registrationRateLimitMiddleware, handleStartRegistration);
  bot.action('start_verification', handleStartVerification);
  bot.action('add_contact_info', handleAddContactInfo);
  bot.action('skip_contact_info', handleSkipContactInfo);
  bot.action('cancel', handleCancelRegistration);

  /**
   * Profile
   */
  bot.action('profile', handleProfile);

  /**
   * Deposits
   */
  bot.action('deposits', handleDeposits);
  bot.action(/^deposit_level_\d+$/, handleDepositLevel);
  bot.action(/^activate_deposit_\d+$/, handleActivateDeposit);
  bot.action('check_pending_deposits', handleCheckPendingDeposits);
  bot.action('deposit_history', handleDepositHistory);
  bot.action(/^deposit_history_\d+$/, handleDepositHistory);
  bot.action(/^cancel_deposit_\d+$/, handleCancelDeposit);

  /**
   * Withdrawals
   */
  bot.action('withdrawals', handleWithdrawals);
  bot.action('request_withdrawal', handleRequestWithdrawal);
  bot.action('withdrawal_history', handleWithdrawalHistory);
  bot.action(/^withdrawal_history_\d+$/, handleWithdrawalHistory);

  /**
   * Transaction History
   */
  bot.action('transaction_history', handleTransactionHistory);
  bot.action(/^transaction_history_\d+$/, handleTransactionHistory);
  bot.action(/^transaction_filter_\w+$/, handleTransactionHistoryFilter);

  /**
   * Referrals
   */
  bot.action('referrals', handleReferrals);
  bot.action('referral_link', handleReferralLink);
  bot.action('referral_stats', handleReferralStats);
  bot.action(/^referral_stats_level_\d+$/, handleReferralStats);
  bot.action('referral_earnings', handleReferralEarnings);
  bot.action(/^referral_earnings_\d+$/, handleReferralEarnings);
  bot.action(/^referral_leaderboard_(referrals|earnings)$/, handleReferralLeaderboard);

  /**
   * Admin panel
   */
  bot.action('admin_panel', handleAdminPanel);
  bot.action('admin_stats', handleAdminStats);
  bot.action(/^admin_stats_\w+$/, handleAdminStats);
  bot.action('admin_broadcast', handleStartBroadcast);
  bot.action('admin_send_to_user', handleStartSendToUser);
  bot.action('admin_ban_user', handleStartBanUser);
  bot.action('admin_unban_user', handleStartUnbanUser);
  bot.action('admin_promote', handleStartPromoteAdmin);
  bot.action('admin_pending_withdrawals', handlePendingWithdrawals);
  bot.action(/^admin_approve_withdrawal_\d+$/, handleApproveWithdrawal);
  bot.action(/^admin_reject_withdrawal_\d+$/, handleRejectWithdrawal);

  /**
   * No-op action (for non-clickable buttons)
   */
  bot.action('noop', async (ctx) => {
    await ctx.answerCbQuery();
  });

  // ==================== TEXT MESSAGES ====================

  /**
   * Handle text messages based on session state
   */
  bot.on('text', async (ctx) => {
    const sessionCtx = ctx as SessionContext;

    switch (sessionCtx.session.state) {
      case BotState.AWAITING_WALLET_ADDRESS:
        await handleWalletInput(ctx);
        break;

      case BotState.AWAITING_CONTACT_INFO:
        await handleContactInfoInput(ctx);
        break;

      case BotState.AWAITING_WITHDRAWAL_AMOUNT:
        await handleWithdrawalAmountInput(ctx);
        break;

      case BotState.AWAITING_WITHDRAWAL_FINANCIAL_PASSWORD:
        await handleWithdrawalPasswordInput(ctx);
        break;

      case BotState.AWAITING_ADMIN_BROADCAST_MESSAGE:
        await handleBroadcastMessage(ctx);
        break;

      case BotState.AWAITING_ADMIN_USER_MESSAGE:
        await handleSendToUserMessage(ctx);
        break;

      case BotState.AWAITING_ADMIN_USER_TO_BAN:
        await handleBanUserInput(ctx);
        break;

      case BotState.AWAITING_ADMIN_USER_TO_UNBAN:
        await handleUnbanUserInput(ctx);
        break;

      case BotState.AWAITING_ADMIN_USER_TO_PROMOTE:
        await handlePromoteAdminInput(ctx);
        break;

      default:
        // Unknown text message
        await ctx.reply(
          'Используйте кнопки меню для навигации или команду /help для помощи.'
        );
    }
  });

  // ==================== ERROR HANDLING ====================

  /**
   * Global error handler
   */
  bot.catch((err, ctx) => {
    logger.error('Bot error', {
      error: err instanceof Error ? err.message : String(err),
      stack: err instanceof Error ? err.stack : undefined,
      updateType: ctx.updateType,
      userId: ctx.from?.id,
    });

    // Try to notify user
    ctx.reply('❌ Произошла ошибка. Пожалуйста, попробуйте позже.').catch(() => {
      // Ignore if can't send message
    });
  });

  logger.info('Telegram bot initialized');

  return bot;
};

/**
 * Start bot with webhook or polling
 */
export const startBot = async (bot: Telegraf): Promise<void> => {
  if (config.telegram.webhookUrl) {
    // Webhook mode (for production)
    await bot.telegram.setWebhook(config.telegram.webhookUrl, {
      secret_token: config.telegram.webhookSecret,
    });

    logger.info('Bot started in webhook mode', {
      webhookUrl: config.telegram.webhookUrl,
    });
  } else {
    // Polling mode (for development)
    await bot.launch();

    logger.info('Bot started in polling mode');

    // Enable graceful stop
    process.once('SIGINT', () => bot.stop('SIGINT'));
    process.once('SIGTERM', () => bot.stop('SIGTERM'));
  }
};

/**
 * Stop bot gracefully
 */
export const stopBot = async (bot: Telegraf): Promise<void> => {
  logger.info('Stopping bot...');
  await bot.stop();
  logger.info('Bot stopped');
};

export default {
  initializeBot,
  startBot,
  stopBot,
};
