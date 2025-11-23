/**
 * Referral Keyboard
 * Keyboards for referral program
 */

import { Markup } from 'telegraf';
import { BUTTON_LABELS } from '../../utils/constants';

/**
 * Get referral menu keyboard
 */
export const getReferralMenuKeyboard = () => {
  return Markup.inlineKeyboard([
    [Markup.button.callback(BUTTON_LABELS.MY_REFERRAL_LINK, 'referral_link')],
    [Markup.button.callback(BUTTON_LABELS.REFERRAL_STATS, 'referral_stats')],
    [Markup.button.callback(BUTTON_LABELS.REFERRAL_EARNINGS, 'referral_earnings')],
    [Markup.button.callback(BUTTON_LABELS.REFERRAL_LEADERBOARD, 'referral_leaderboard_referrals')],
    [Markup.button.callback(BUTTON_LABELS.BACK, 'main_menu')],
  ]);
};

/**
 * Get referral stats keyboard with navigation
 * @param level - Current level being viewed (1-3)
 */
export const getReferralStatsKeyboard = (level: number = 1) => {
  const buttons: any[][] = [];

  // Level selection buttons
  const levelButtons = [];
  for (let i = 1; i <= 3; i++) {
    const emoji = i === level ? '✅' : '📊';
    levelButtons.push(
      Markup.button.callback(`${emoji} Уровень ${i}`, `referral_stats_level_${i}`)
    );
  }
  buttons.push(levelButtons);

  // Back button
  buttons.push([
    Markup.button.callback(BUTTON_LABELS.BACK, 'referrals'),
  ]);

  return Markup.inlineKeyboard(buttons);
};

/**
 * Get referral earnings keyboard with pagination
 * @param currentPage - Current page number
 * @param totalPages - Total number of pages
 */
export const getReferralEarningsKeyboard = (
  currentPage: number,
  totalPages: number
) => {
  const buttons: any[][] = [];

  if (totalPages > 1) {
    const navButtons = [];

    if (currentPage > 1) {
      navButtons.push(
        Markup.button.callback('⬅️', `referral_earnings_${currentPage - 1}`)
      );
    }

    navButtons.push(
      Markup.button.callback(`${currentPage}/${totalPages}`, 'noop')
    );

    if (currentPage < totalPages) {
      navButtons.push(
        Markup.button.callback('➡️', `referral_earnings_${currentPage + 1}`)
      );
    }

    buttons.push(navButtons);
  }

  buttons.push([
    Markup.button.callback(BUTTON_LABELS.BACK, 'referrals'),
  ]);

  return Markup.inlineKeyboard(buttons);
};

export default {
  getReferralMenuKeyboard,
  getReferralStatsKeyboard,
  getReferralEarningsKeyboard,
};
