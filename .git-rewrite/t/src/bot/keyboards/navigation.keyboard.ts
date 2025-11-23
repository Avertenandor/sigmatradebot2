/**
 * Navigation Keyboard
 * Back button and navigation utilities
 */

import { Markup } from 'telegraf';
import { BUTTON_LABELS } from '../../utils/constants';

/**
 * Get back button keyboard
 * @param callbackData - Callback data for back button
 */
export const getBackButton = (callbackData: string = 'main_menu') => {
  return Markup.inlineKeyboard([
    [Markup.button.callback(BUTTON_LABELS.BACK, callbackData)],
  ]);
};

/**
 * Get back to main menu button
 */
export const getMainMenuButton = () => {
  return Markup.inlineKeyboard([
    [Markup.button.callback(BUTTON_LABELS.MAIN_MENU, 'main_menu')],
  ]);
};

/**
 * Get cancel button
 */
export const getCancelButton = () => {
  return Markup.inlineKeyboard([
    [Markup.button.callback(BUTTON_LABELS.CANCEL, 'cancel')],
  ]);
};

/**
 * Add back button to existing keyboard
 * @param keyboard - Existing keyboard
 * @param callbackData - Callback data for back button
 */
export const addBackButton = (
  keyboard: any[][],
  callbackData: string = 'main_menu'
) => {
  return [
    ...keyboard,
    [Markup.button.callback(BUTTON_LABELS.BACK, callbackData)],
  ];
};

export default {
  getBackButton,
  getMainMenuButton,
  getCancelButton,
  addBackButton,
};
