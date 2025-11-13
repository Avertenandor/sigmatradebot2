/**
 * Admin Wallets Handler
 * Manages system and payout wallet addresses through approval workflow
 *
 * FEATURES:
 * - View current wallet addresses and balances
 * - Create wallet change requests (Extended Admin / Super Admin)
 * - Approve/Reject/Apply requests (Super Admin only)
 * - Reload blockchain monitors after wallet changes
 *
 * SECURITY:
 * - Extended Admin can stage changes, but cannot apply
 * - Super Admin must approve and apply all changes
 * - Private keys handled securely via Secret Manager
 * - All actions audited in financial log
 */

import { Context, Markup } from 'telegraf';
import { AdminContext } from '../../middlewares/admin.middleware';
import { ERROR_MESSAGES } from '../../../utils/constants';
import { walletAdminService } from '../../../services/wallet-admin.service';
import { settingsService } from '../../../services/settings.service';
import { logAdminAction } from '../../../utils/logger.util';
import { requireAuthenticatedAdmin } from './utils';
import { Admin } from '../../../database/entities';

// FSM states for wallet change flow
interface WalletChangeState {
  type?: 'system_deposit' | 'payout_withdrawal';
  newAddress?: string;
  step?: 'address' | 'key' | 'confirm';
}

const walletChangeStates = new Map<number, WalletChangeState>();

/**
 * Show wallet management main menu
 */
export const handleWalletsMenu = async (ctx: Context): Promise<void> => {
  const adminCtx = ctx as AdminContext;

  if (!adminCtx.isAdmin) {
    await ctx.answerCbQuery?.(ERROR_MESSAGES.ADMIN_ONLY);
    return;
  }

  if (!(await requireAuthenticatedAdmin(ctx))) {
    return;
  }

  const admin = adminCtx.admin as Admin;

  try {
    // Get current wallet addresses
    const systemWallet = await settingsService.getSystemWalletAddress();
    const payoutWallet = await settingsService.getPayoutWalletAddress();
    const walletsVersion = await settingsService.getWalletsVersion();

    // TODO: Get balances from blockchain service
    // const systemBalance = await blockchainService.getBalance(systemWallet);
    // const payoutBalance = await blockchainService.getBalance(payoutWallet);

    const message = `
🔐 **Кошельки системы**

**Кошелёк приёма депозитов:**
\`${systemWallet}\`
💰 Баланс: - USDT (загрузка...)

**Кошелёк выплат:**
\`${payoutWallet}\`
💰 Баланс: - USDT (загрузка...)
⛽ Gas (BNB): - BNB (загрузка...)

📌 **Версия:** v${walletsVersion}

⚡ **Ваша роль:** ${admin.roleDisplay}
${admin.canStageWalletChanges ? '✅ Может создавать заявки на смену' : ''}
${admin.canApproveWalletChanges ? '✅ Может одобрять и применять' : ''}
    `.trim();

    const buttons = [];

    // Extended Admin and Super Admin can stage changes
    if (admin.canStageWalletChanges) {
      buttons.push([
        Markup.button.callback('✏️ Изменить адрес приёма', 'admin_wallet_change_system'),
        Markup.button.callback('✏️ Изменить кошелёк выплат', 'admin_wallet_change_payout'),
      ]);
    }

    // All admins can view requests
    buttons.push([Markup.button.callback('📥 Заявки на смену', 'admin_wallet_requests')]);

    // Super Admin only features
    if (admin.isSuperAdmin) {
      buttons.push([
        Markup.button.callback('♻️ Перезапустить мониторинг', 'admin_wallet_reload_monitor'),
      ]);
    }

    buttons.push([Markup.button.callback('« Назад', 'admin_panel')]);

    const keyboard = Markup.inlineKeyboard(buttons);

    if (ctx.callbackQuery && 'message' in ctx.callbackQuery) {
      await ctx.editMessageText(message, {
        parse_mode: 'Markdown',
        ...keyboard,
      });
    } else {
      await ctx.reply(message, {
        parse_mode: 'Markdown',
        ...keyboard,
      });
    }

    if (ctx.callbackQuery) {
      await ctx.answerCbQuery?.();
    }

    logAdminAction(ctx.from!.id, 'viewed_wallet_management', {});
  } catch (error) {
    await ctx.reply('Ошибка загрузки данных кошельков');
    if (ctx.callbackQuery) {
      await ctx.answerCbQuery?.();
    }
  }
};

/**
 * Start wallet change flow - Step 1: Ask for address
 */
export const handleStartWalletChange = async (ctx: Context, type: 'system_deposit' | 'payout_withdrawal'): Promise<void> => {
  const adminCtx = ctx as AdminContext;
  const admin = adminCtx.admin as Admin;

  if (!admin.canStageWalletChanges) {
    await ctx.answerCbQuery?.('Недостаточно прав');
    return;
  }

  if (!(await requireAuthenticatedAdmin(ctx))) {
    return;
  }

  // Initialize state
  walletChangeStates.set(ctx.from!.id, { type, step: 'address' });

  const typeDisplay = type === 'system_deposit' ? 'адреса приёма депозитов' : 'кошелька выплат';

  const message = `
🔐 **Смена ${typeDisplay}**

📝 **Шаг 1:** Введите новый адрес кошелька (BSC/BEP-20)

⚠️ **Внимание:**
• Адрес должен быть в формате checksummed (EIP-55)
• Проверьте адрес несколько раз перед отправкой
• Заявка требует одобрения Super Admin

Отправьте адрес кошелька или /cancel для отмены.
  `.trim();

  await ctx.reply(message, {
    parse_mode: 'Markdown',
    ...Markup.inlineKeyboard([[Markup.button.callback('❌ Отменить', 'admin_wallets')]]),
  });

  if (ctx.callbackQuery) {
    await ctx.answerCbQuery?.();
  }
};

/**
 * Handle address input (Step 2 for system, Step 2a for payout)
 */
export const handleAddressInput = async (ctx: Context): Promise<boolean> => {
  const userId = ctx.from!.id;
  const state = walletChangeStates.get(userId);

  if (!state || state.step !== 'address') {
    return false; // Not in wallet change flow
  }

  const address = ctx.message && 'text' in ctx.message ? ctx.message.text.trim() : '';

  if (!address) {
    await ctx.reply('Пожалуйста, отправьте адрес кошелька');
    return true;
  }

  // Validate address format
  // TODO: Use validation util
  if (!/^0x[a-fA-F0-9]{40}$/.test(address)) {
    await ctx.reply('❌ Неверный формат адреса. Адрес должен начинаться с 0x и содержать 42 символа.');
    return true;
  }

  state.newAddress = address;

  if (state.type === 'system_deposit') {
    // System wallet: no key needed, go straight to confirmation
    state.step = 'confirm';
    await showConfirmation(ctx, state);
  } else {
    // Payout wallet: need private key/mnemonic
    state.step = 'key';
    const message = `
✅ Адрес принят: \`${address}\`

🔐 **Шаг 2:** Введите приватный ключ или сид-фразу

⚠️ **Важно:**
• Приватный ключ: должен начинаться с 0x (66 символов)
• Сид-фраза: 12 или 24 слова через пробел
• Ключ будет сохранён в Google Secret Manager
• Ключ будет проверен на соответствие адресу

Отправьте ключ или /cancel для отмены.
    `.trim();

    await ctx.reply(message, {
      parse_mode: 'Markdown',
      ...Markup.inlineKeyboard([[Markup.button.callback('❌ Отменить', 'admin_wallets')]]),
    });
  }

  walletChangeStates.set(userId, state);
  return true;
};

/**
 * Handle key input (Step 2b for payout only)
 */
export const handleKeyInput = async (ctx: Context): Promise<boolean> => {
  const userId = ctx.from!.id;
  const state = walletChangeStates.get(userId);

  if (!state || state.step !== 'key' || state.type !== 'payout_withdrawal') {
    return false;
  }

  const key = ctx.message && 'text' in ctx.message ? ctx.message.text.trim() : '';

  if (!key) {
    await ctx.reply('Пожалуйста, отправьте приватный ключ или сид-фразу');
    return true;
  }

  // Delete message with private key immediately
  try {
    if (ctx.message) {
      await ctx.deleteMessage(ctx.message.message_id);
    }
  } catch (error) {
    // Ignore deletion errors
  }

  // Validate key format (basic check)
  const isPrivateKey = key.startsWith('0x') && key.length === 66;
  const isMnemonic = key.split(/\s+/).length === 12 || key.split(/\s+/).length === 24;

  if (!isPrivateKey && !isMnemonic) {
    await ctx.reply('❌ Неверный формат. Ожидается приватный ключ (0x...) или сид-фраза (12/24 слова)');
    return true;
  }

  // Store key temporarily (will be validated and stored in Secret Manager in next step)
  (state as any).tempKey = key;
  state.step = 'confirm';

  await showConfirmation(ctx, state);
  walletChangeStates.set(userId, state);
  return true;
};

/**
 * Show confirmation before creating request
 */
const showConfirmation = async (ctx: Context, state: WalletChangeState): Promise<void> => {
  const typeDisplay = state.type === 'system_deposit' ? 'адреса приёма депозитов' : 'кошелька выплат';
  const hasKey = state.type === 'payout_withdrawal';

  const message = `
✅ **Подтверждение смены ${typeDisplay}**

📍 **Новый адрес:** \`${state.newAddress}\`
🔐 **Приватный ключ:** ${hasKey ? '✅ Получен и будет сохранён в Secret Manager' : '⏭️ Не требуется'}

⚠️ **Что произойдёт дальше:**
1. Будет создана заявка на смену (статус: pending)
2. Super Admin должен одобрить заявку
3. Super Admin должен применить изменения
4. Мониторинг будет перезапущен с новым адресом

Подтвердить создание заявки?
  `.trim();

  await ctx.reply(message, {
    parse_mode: 'Markdown',
    ...Markup.inlineKeyboard([
      [
        Markup.button.callback('✅ Подтвердить', 'admin_wallet_confirm_create'),
        Markup.button.callback('❌ Отменить', 'admin_wallet_cancel'),
      ],
    ]),
  });
};

/**
 * Confirm and create request
 */
export const handleConfirmCreate = async (ctx: Context): Promise<void> => {
  const adminCtx = ctx as AdminContext;
  const admin = adminCtx.admin as Admin;
  const userId = ctx.from!.id;
  const state = walletChangeStates.get(userId);

  if (!state || state.step !== 'confirm') {
    await ctx.answerCbQuery?.('Сессия истекла. Начните заново.');
    return;
  }

  if (!(await requireAuthenticatedAdmin(ctx))) {
    return;
  }

  try {
    await ctx.answerCbQuery?.('Создание заявки...');

    // Create request
    const request = await walletAdminService.createRequest(
      state.type!,
      state.newAddress!,
      admin.id,
      (state as any).tempKey,
      'Создано через админ-панель'
    );

    // Clear temp key from memory
    delete (state as any).tempKey;
    walletChangeStates.delete(userId);

    const message = `
✅ **Заявка создана успешно**

🆔 **ID заявки:** #${request.id}
📋 **Тип:** ${request.typeDisplay}
📍 **Новый адрес:** \`${request.new_address}\`
📊 **Статус:** ${request.statusDisplay}

Заявка ожидает одобрения Super Admin.
    `.trim();

    await ctx.editMessageText(message, {
      parse_mode: 'Markdown',
      ...Markup.inlineKeyboard([
        [Markup.button.callback('📥 Мои заявки', 'admin_wallet_requests')],
        [Markup.button.callback('« Назад', 'admin_wallets')],
      ]),
    });

    logAdminAction(admin.telegram_id, 'wallet_change_request_created', {
      requestId: request.id,
      type: state.type,
    });
  } catch (error: any) {
    await ctx.editMessageText(`❌ Ошибка создания заявки: ${error.message}`, {
      ...Markup.inlineKeyboard([[Markup.button.callback('« Назад', 'admin_wallets')]]),
    });
  }
};

/**
 * Cancel wallet change flow
 */
export const handleCancelWalletChange = async (ctx: Context): Promise<void> => {
  const userId = ctx.from!.id;
  const state = walletChangeStates.get(userId);

  if (state) {
    // Clear temp key from memory
    delete (state as any).tempKey;
    walletChangeStates.delete(userId);
  }

  await ctx.editMessageText('❌ Операция отменена', {
    ...Markup.inlineKeyboard([[Markup.button.callback('« Назад', 'admin_wallets')]]),
  });

  if (ctx.callbackQuery) {
    await ctx.answerCbQuery?.();
  }
};

/**
 * Show all wallet change requests
 */
export const handleViewRequests = async (ctx: Context): Promise<void> => {
  const adminCtx = ctx as AdminContext;

  if (!adminCtx.isAdmin) {
    await ctx.answerCbQuery?.(ERROR_MESSAGES.ADMIN_ONLY);
    return;
  }

  if (!(await requireAuthenticatedAdmin(ctx))) {
    return;
  }

  try {
    const requests = await walletAdminService.getRequests({ limit: 20 });

    if (requests.length === 0) {
      await ctx.editMessageText('📥 Заявок на смену кошельков нет', {
        ...Markup.inlineKeyboard([[Markup.button.callback('« Назад', 'admin_wallets')]]),
      });
      if (ctx.callbackQuery) {
        await ctx.answerCbQuery?.();
      }
      return;
    }

    const requestsList = requests.map((req) => {
      return `
🆔 **#${req.id}** | ${req.statusDisplay}
📋 ${req.typeDisplay}
📍 \`${req.new_address.substring(0, 10)}...${req.new_address.substring(38)}\`
👤 Инициатор: ${req.initiated_by.displayName}
📅 ${req.created_at.toLocaleDateString('ru-RU')}
      `.trim();
    }).join('\n\n');

    const message = `
📥 **Заявки на смену кошельков**

${requestsList}

Выберите заявку для деталей:
    `.trim();

    const buttons = requests.slice(0, 10).map((req) => [
      Markup.button.callback(`#${req.id} ${req.statusDisplay}`, `admin_wallet_request_${req.id}`),
    ]);
    buttons.push([Markup.button.callback('« Назад', 'admin_wallets')]);

    await ctx.editMessageText(message, {
      parse_mode: 'Markdown',
      ...Markup.inlineKeyboard(buttons),
    });

    if (ctx.callbackQuery) {
      await ctx.answerCbQuery?.();
    }
  } catch (error) {
    await ctx.reply('Ошибка загрузки заявок');
    if (ctx.callbackQuery) {
      await ctx.answerCbQuery?.();
    }
  }
};

/**
 * Show request details
 */
export const handleViewRequestDetails = async (ctx: Context, requestId: number): Promise<void> => {
  const adminCtx = ctx as AdminContext;
  const admin = adminCtx.admin as Admin;

  if (!adminCtx.isAdmin) {
    await ctx.answerCbQuery?.(ERROR_MESSAGES.ADMIN_ONLY);
    return;
  }

  if (!(await requireAuthenticatedAdmin(ctx))) {
    return;
  }

  try {
    const request = await walletAdminService.getRequest(requestId);

    if (!request) {
      await ctx.answerCbQuery?.('Заявка не найдена');
      return;
    }

    const message = `
📋 **Заявка #${request.id}**

📊 **Статус:** ${request.statusDisplay}
📋 **Тип:** ${request.typeDisplay}
📍 **Новый адрес:** \`${request.new_address}\`

👤 **Инициатор:** ${request.initiated_by.displayName}
📅 **Создано:** ${request.created_at.toLocaleString('ru-RU')}

${request.approved_by ? `✅ **Одобрил:** ${request.approved_by.displayName}\n📅 **Одобрено:** ${request.approved_at?.toLocaleString('ru-RU')}` : ''}

${request.applied_at ? `🚀 **Применено:** ${request.applied_at.toLocaleString('ru-RU')}` : ''}

${request.reason ? `📝 **Причина/комментарий:**\n${request.reason}` : ''}
    `.trim();

    const buttons = [];

    // Super Admin actions
    if (admin.isSuperAdmin) {
      if (request.status === 'pending') {
        buttons.push([
          Markup.button.callback('✅ Одобрить', `admin_wallet_approve_${requestId}`),
          Markup.button.callback('❌ Отклонить', `admin_wallet_reject_${requestId}`),
        ]);
      }

      if (request.status === 'approved') {
        buttons.push([
          Markup.button.callback('🚀 Применить', `admin_wallet_apply_${requestId}`),
        ]);
      }
    }

    buttons.push([Markup.button.callback('« Назад к списку', 'admin_wallet_requests')]);

    await ctx.editMessageText(message, {
      parse_mode: 'Markdown',
      ...Markup.inlineKeyboard(buttons),
    });

    if (ctx.callbackQuery) {
      await ctx.answerCbQuery?.();
    }
  } catch (error) {
    await ctx.reply('Ошибка загрузки заявки');
    if (ctx.callbackQuery) {
      await ctx.answerCbQuery?.();
    }
  }
};

/**
 * Approve request (Super Admin only)
 */
export const handleApproveRequest = async (ctx: Context, requestId: number): Promise<void> => {
  const adminCtx = ctx as AdminContext;
  const admin = adminCtx.admin as Admin;

  if (!admin.isSuperAdmin) {
    await ctx.answerCbQuery?.('Только Super Admin может одобрять заявки');
    return;
  }

  if (!(await requireAuthenticatedAdmin(ctx))) {
    return;
  }

  try {
    await ctx.answerCbQuery?.('Одобрение заявки...');

    const request = await walletAdminService.approveRequest(requestId, admin.id);

    await ctx.editMessageText(
      `✅ Заявка #${requestId} одобрена!\n\nТеперь её можно применить.`,
      {
        ...Markup.inlineKeyboard([
          [Markup.button.callback('🚀 Применить', `admin_wallet_apply_${requestId}`)],
          [Markup.button.callback('« Назад', `admin_wallet_request_${requestId}`)],
        ]),
      }
    );

    logAdminAction(admin.telegram_id, 'wallet_change_request_approved', { requestId });
  } catch (error: any) {
    await ctx.editMessageText(`❌ Ошибка одобрения: ${error.message}`, {
      ...Markup.inlineKeyboard([[Markup.button.callback('« Назад', `admin_wallet_request_${requestId}`)]]),
    });
  }
};

/**
 * Reject request (Super Admin only)
 */
export const handleRejectRequest = async (ctx: Context, requestId: number): Promise<void> => {
  const adminCtx = ctx as AdminContext;
  const admin = adminCtx.admin as Admin;

  if (!admin.isSuperAdmin) {
    await ctx.answerCbQuery?.('Только Super Admin может отклонять заявки');
    return;
  }

  if (!(await requireAuthenticatedAdmin(ctx))) {
    return;
  }

  try {
    await ctx.answerCbQuery?.('Отклонение заявки...');

    const request = await walletAdminService.rejectRequest(
      requestId,
      admin.id,
      'Отклонено через админ-панель'
    );

    await ctx.editMessageText(
      `❌ Заявка #${requestId} отклонена`,
      {
        ...Markup.inlineKeyboard([[Markup.button.callback('« Назад', 'admin_wallet_requests')]]),
      }
    );

    logAdminAction(admin.telegram_id, 'wallet_change_request_rejected', { requestId });
  } catch (error: any) {
    await ctx.editMessageText(`❌ Ошибка отклонения: ${error.message}`, {
      ...Markup.inlineKeyboard([[Markup.button.callback('« Назад', `admin_wallet_request_${requestId}`)]]),
    });
  }
};

/**
 * Apply request (Super Admin only)
 */
export const handleApplyRequest = async (ctx: Context, requestId: number): Promise<void> => {
  const adminCtx = ctx as AdminContext;
  const admin = adminCtx.admin as Admin;

  if (!admin.isSuperAdmin) {
    await ctx.answerCbQuery?.('Только Super Admin может применять заявки');
    return;
  }

  if (!(await requireAuthenticatedAdmin(ctx))) {
    return;
  }

  try {
    await ctx.answerCbQuery?.('Применение изменений...');

    const request = await walletAdminService.applyRequest(requestId, admin.id);

    await ctx.editMessageText(
      `🚀 **Заявка #${requestId} успешно применена!**\n\n✅ Кошелёк обновлён\n✅ Мониторинг перезапущен`,
      {
        parse_mode: 'Markdown',
        ...Markup.inlineKeyboard([[Markup.button.callback('« Назад к кошелькам', 'admin_wallets')]]),
      }
    );

    logAdminAction(admin.telegram_id, 'wallet_change_request_applied', { requestId });
  } catch (error: any) {
    await ctx.editMessageText(`❌ Ошибка применения: ${error.message}`, {
      ...Markup.inlineKeyboard([[Markup.button.callback('« Назад', `admin_wallet_request_${requestId}`)]]),
    });
  }
};
