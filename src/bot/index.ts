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
  requireAuthenticated,
  rateLimitMiddleware,
  registrationRateLimitMiddleware,
} from './middlewares';
import { requestIdMiddleware } from './middlewares/request-id.middleware';
import { updateSessionState, clearSession } from './middlewares/session.middleware';
import { BotState } from '../utils/constants';

// Handlers
import {
  handleStart,
  handleMainMenu,
  handleHelp,
  handleStartRegistration,
  handleWalletInput,
  handleConfirmWalletAddress,
  handleReenterWalletAddress,
  handleStartVerification,
  handleAddContactInfo,
  handleContactInfoInput,
  handleSkipContactInfo,
  handleCancelRegistration,
  handleShowPasswordAgain,
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
  handleCancelWithdrawal,
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
  handleListAdmins,
  handleRemoveAdmin,
  handleRegenerateMasterKey,
  handleAdminLogin,
  handleMasterKeyInput,
  handleAdminLogout,
  handleAdminSession,
  handleRewardSessions,
  handleRewardStats,
  handleCalculateRewards,
  handleToggleSession,
  handleDeleteSession,
  handleStartCreateSession,
  handleRewardSessionInput,
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
  // IMPORTANT: requestIdMiddleware MUST be first for end-to-end request tracking
  bot.use(requestIdMiddleware);
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

  /**
   * /reset command
   * FIX #8: Allow users to manually reset their session state
   */
  bot.command('reset', async (ctx) => {
    const userId = ctx.from.id;

    await clearSession(userId);

    await ctx.reply(
      '🔄 **Сессия сброшена**\n\n' +
      'Все временные данные очищены.\n' +
      'Вы можете начать заново.\n\n' +
      'Используйте /start для входа.',
      { parse_mode: 'Markdown' }
    );

    logger.info('User manually reset session', { userId });
  });

  /**
   * Admin authentication commands
   */
  bot.command('admin_login', handleAdminLogin);
  bot.command('admin_logout', handleAdminLogout);
  bot.command('admin_session', handleAdminSession);

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
  bot.action('confirm_wallet_address', handleConfirmWalletAddress); // FIX #15
  bot.action('reenter_wallet_address', handleReenterWalletAddress); // FIX #15
  bot.action('start_verification', handleStartVerification);
  bot.action('add_contact_info', handleAddContactInfo);
  bot.action('skip_contact_info', handleSkipContactInfo);
  bot.action('cancel', handleCancelRegistration);
  bot.action('show_password_again', handleShowPasswordAgain); // FIX #6

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
  bot.action(/^cancel_withdrawal_\d+$/, handleCancelWithdrawal);

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
  bot.action('admin_list_admins', handleListAdmins);
  bot.action(/^admin_remove_\d+$/, handleRemoveAdmin);
  bot.action(/^admin_regenerate_key_\d+$/, handleRegenerateMasterKey);
  bot.action('admin_pending_withdrawals', handlePendingWithdrawals);
  bot.action(/^admin_approve_withdrawal_\d+$/, handleApproveWithdrawal);
  bot.action(/^admin_reject_withdrawal_\d+$/, handleRejectWithdrawal);

  /**
   * Reward sessions
   */
  bot.action('reward_sessions', handleRewardSessions);
  bot.action(/^reward_stats_\d+$/, handleRewardStats);
  bot.action(/^reward_calculate_\d+$/, handleCalculateRewards);
  bot.action(/^reward_toggle_\d+$/, handleToggleSession);
  bot.action(/^reward_delete_\d+$/, handleDeleteSession);
  bot.action('reward_create', handleStartCreateSession);

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

      case BotState.AWAITING_ADMIN_MASTER_KEY:
        await handleMasterKeyInput(ctx);
        break;

      case BotState.AWAITING_REWARD_SESSION_DATA:
        await handleRewardSessionInput(ctx);
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
   * FIX #8: Reset session state on error to prevent stuck users
   */
  bot.catch(async (err, ctx) => {
    const userId = ctx.from?.id;

    logger.error('Bot error', {
      error: err instanceof Error ? err.message : String(err),
      stack: err instanceof Error ? err.stack : undefined,
      updateType: ctx.updateType,
      userId,
    });

    // RESET SESSION STATE TO PREVENT STUCK USERS (FIX #8)
    if (userId) {
      try {
        await updateSessionState(userId, BotState.IDLE);
        logger.info('Session state reset to IDLE after error', { userId });
      } catch (stateError) {
        logger.error('Failed to reset session state', {
          userId,
          error: stateError,
        });
      }
    }

    // Send user-friendly error message with recovery instructions
    try {
      await ctx.reply(
        '❌ Произошла ошибка при обработке вашего запроса.\n\n' +
        '🔄 Состояние сброшено. Вы можете продолжить работу.\n\n' +
        'Используйте /start для возврата в главное меню или /help для помощи.\n\n' +
        'Если проблема повторяется, свяжитесь с поддержкой.'
      );
    } catch (replyError) {
      logger.error('Failed to send error message to user', {
        userId,
        error: replyError,
      });
    }
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
