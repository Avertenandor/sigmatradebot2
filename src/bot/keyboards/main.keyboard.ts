/**
 * Main Keyboard
 * Primary navigation keyboard for registered users
 */

import { Markup } from 'telegraf';
import { BUTTON_LABELS } from '../../utils/constants';

/**
 * Get main menu keyboard
 * @param isAdmin - Whether user is admin
 */
export const getMainKeyboard = (isAdmin: boolean = false) => {
  const buttons = [
    [
      Markup.button.callback(BUTTON_LABELS.PROFILE, 'profile'),
      Markup.button.callback(BUTTON_LABELS.DEPOSITS, 'deposits'),
    ],
    [
      Markup.button.callback(BUTTON_LABELS.WITHDRAWALS, 'withdrawals'),
      Markup.button.callback(BUTTON_LABELS.REFERRALS, 'referrals'),
    ],
    [
      Markup.button.callback(BUTTON_LABELS.TRANSACTIONS, 'transaction_history'),
    ],
    [
      Markup.button.callback(BUTTON_LABELS.SUPPORT, 'support'),
    ],
    [
      Markup.button.callback(BUTTON_LABELS.HELP, 'help'),
    ],
  ];

  // Add admin panel button for admins
  if (isAdmin) {
    buttons.push([
      Markup.button.callback(BUTTON_LABELS.ADMIN_PANEL, 'admin_panel'),
    ]);
  }

  return Markup.inlineKeyboard(buttons);
};

/**
 * Get welcome keyboard for new users
 */
export const getWelcomeKeyboard = () => {
  return Markup.inlineKeyboard([
    [Markup.button.callback(BUTTON_LABELS.START_REGISTRATION, 'start_registration')],
  ]);
};

export default {
  getMainKeyboard,
  getWelcomeKeyboard,
};
