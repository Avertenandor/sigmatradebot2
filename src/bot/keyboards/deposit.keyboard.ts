/**
 * Deposit Keyboard
 * Keyboards for deposit operations
 */

import { Markup } from 'telegraf';
import { BUTTON_LABELS, DEPOSIT_LEVELS } from '../../utils/constants';

/**
 * Get deposit levels keyboard
 * Shows ONLY activated + available levels (hides closed levels completely)
 * @param activatedLevels - Array of already activated levels
 * @param availableLevels - Array of levels available for activation
 */
export const getDepositLevelsKeyboard = (
  activatedLevels: number[] = [],
  availableLevels: number[] = []
) => {
  const buttons: any[][] = [];

  // Combine activated and available levels (show only these)
  const shownLevels = Array.from(new Set([...activatedLevels, ...availableLevels])).sort((a, b) => a - b);

  // Create buttons only for shown levels
  for (const level of shownLevels) {
    const amount = DEPOSIT_LEVELS[level as keyof typeof DEPOSIT_LEVELS];
    const buttonText = activatedLevels.includes(level)
      ? `✅ Уровень ${level}: ${amount} USDT`
      : `💵 Уровень ${level}: ${amount} USDT`;

    buttons.push([
      Markup.button.callback(buttonText, `deposit_level_${level}`),
    ]);
  }

  // Add status checker and history buttons
  buttons.push([
    Markup.button.callback('⏳ Проверить статус', 'check_pending_deposits'),
    Markup.button.callback(BUTTON_LABELS.DEPOSIT_HISTORY, 'deposit_history'),
  ]);

  // Add back button
  buttons.push([
    Markup.button.callback(BUTTON_LABELS.BACK, 'main_menu'),
  ]);

  return Markup.inlineKeyboard(buttons);
};

/**
 * Get deposit info keyboard for a specific level
 * @param level - Deposit level
 * @param canActivate - Whether user can activate this level
 */
export const getDepositInfoKeyboard = (
  level: number,
  canActivate: boolean = false
) => {
  const buttons: any[][] = [];

  if (canActivate) {
    buttons.push([
      Markup.button.callback(
        `💰 Активировать уровень ${level}`,
        `activate_deposit_${level}`
      ),
    ]);
  }

  buttons.push([
    Markup.button.callback(BUTTON_LABELS.BACK, 'deposits'),
  ]);

  return Markup.inlineKeyboard(buttons);
};

/**
 * Get deposit history navigation keyboard
 * @param currentPage - Current page number
 * @param totalPages - Total number of pages
 */
export const getDepositHistoryKeyboard = (
  currentPage: number,
  totalPages: number
) => {
  const buttons: any[][] = [];

  if (totalPages > 1) {
    const navButtons = [];

    if (currentPage > 1) {
      navButtons.push(
        Markup.button.callback('⬅️ Назад', `deposit_history_${currentPage - 1}`)
      );
    }

    navButtons.push(
      Markup.button.callback(`${currentPage}/${totalPages}`, 'noop')
    );

    if (currentPage < totalPages) {
      navButtons.push(
        Markup.button.callback('Вперед ➡️', `deposit_history_${currentPage + 1}`)
      );
    }

    buttons.push(navButtons);
  }

  buttons.push([
    Markup.button.callback(BUTTON_LABELS.BACK, 'deposits'),
  ]);

  return Markup.inlineKeyboard(buttons);
};

export default {
  getDepositLevelsKeyboard,
  getDepositInfoKeyboard,
  getDepositHistoryKeyboard,
};
