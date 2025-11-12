/**
 * Admin Keyboard
 * Keyboards for admin panel
 */

import { Markup } from 'telegraf';
import { BUTTON_LABELS } from '../../utils/constants';

/**
 * Get admin panel main keyboard
 */
export const getAdminPanelKeyboard = () => {
  return Markup.inlineKeyboard([
    [Markup.button.callback(BUTTON_LABELS.PENDING_WITHDRAWALS, 'admin_pending_withdrawals')],
    [Markup.button.callback('🔑 Финпароли', 'admin_finpass_list')],
    [
      Markup.button.callback('💰 Сессии наград', 'reward_sessions'),
      Markup.button.callback(BUTTON_LABELS.PLATFORM_STATS, 'admin_stats'),
    ],
    [Markup.button.callback('⚙️ Депозиты', 'admin_deposit_settings')],
    [Markup.button.callback('🛑 Чёрный список', 'admin_blacklist')],
    [Markup.button.callback('🆘 Техподдержка', 'admin_support')],
    [Markup.button.callback(BUTTON_LABELS.BROADCAST_MESSAGE, 'admin_broadcast')],
    [Markup.button.callback(BUTTON_LABELS.SEND_TO_USER, 'admin_send_to_user')],
    [
      Markup.button.callback(BUTTON_LABELS.BAN_USER, 'admin_ban_user'),
      Markup.button.callback(BUTTON_LABELS.UNBAN_USER, 'admin_unban_user'),
    ],
    [
      Markup.button.callback(BUTTON_LABELS.PROMOTE_ADMIN, 'admin_promote'),
      Markup.button.callback('📋 Список админов', 'admin_list_admins'),
    ],
    [Markup.button.callback(BUTTON_LABELS.BACK, 'main_menu')],
  ]);
};

/**
 * Get admin confirmation keyboard
 * @param action - Action to confirm
 * @param data - Data associated with action
 */
export const getAdminConfirmationKeyboard = (action: string, data?: string) => {
  const confirmCallback = data ? `admin_confirm_${action}_${data}` : `admin_confirm_${action}`;

  return Markup.inlineKeyboard([
    [
      Markup.button.callback('✅ Подтвердить', confirmCallback),
      Markup.button.callback('❌ Отмена', 'admin_panel'),
    ],
  ]);
};

/**
 * Get admin stats keyboard with time range selection
 * @param selectedRange - Currently selected time range
 */
export const getAdminStatsKeyboard = (selectedRange: string = 'today') => {
  return Markup.inlineKeyboard([
    [
      Markup.button.callback(
        selectedRange === 'today' ? '✅ Сегодня' : '📊 Сегодня',
        'admin_stats_today'
      ),
      Markup.button.callback(
        selectedRange === 'week' ? '✅ Неделя' : '📊 Неделя',
        'admin_stats_week'
      ),
    ],
    [
      Markup.button.callback(
        selectedRange === 'month' ? '✅ Месяц' : '📊 Месяц',
        'admin_stats_month'
      ),
      Markup.button.callback(
        selectedRange === 'all' ? '✅ Всё время' : '📊 Всё время',
        'admin_stats_all'
      ),
    ],
    [Markup.button.callback(BUTTON_LABELS.BACK, 'admin_panel')],
  ]);
};

export default {
  getAdminPanelKeyboard,
  getAdminConfirmationKeyboard,
  getAdminStatsKeyboard,
};
