/**
 * Telegram Bot Mock
 * Mock Telegraf bot for testing bot handlers
 */

import { Context } from 'telegraf';

/**
 * Create mock Telegram context
 */
export function createMockContext(overrides: Partial<Context> = {}): Context {
  const mockContext = {
    // User
    from: {
      id: 123456789,
      is_bot: false,
      first_name: 'Test',
      last_name: 'User',
      username: 'testuser',
      language_code: 'en',
    },

    // Chat
    chat: {
      id: 123456789,
      type: 'private',
      first_name: 'Test',
      last_name: 'User',
      username: 'testuser',
    },

    // Message
    message: {
      message_id: 1,
      date: Math.floor(Date.now() / 1000),
      chat: {
        id: 123456789,
        type: 'private',
        first_name: 'Test',
        last_name: 'User',
        username: 'testuser',
      },
      from: {
        id: 123456789,
        is_bot: false,
        first_name: 'Test',
        last_name: 'User',
        username: 'testuser',
        language_code: 'en',
      },
      text: '',
    },

    // Update
    update: {
      update_id: 1,
    },

    // Update type
    updateType: 'message',

    // Text
    text: '',

    // Methods
    reply: jest.fn().mockResolvedValue({ message_id: 2 }),
    replyWithMarkdown: jest.fn().mockResolvedValue({ message_id: 3 }),
    replyWithHTML: jest.fn().mockResolvedValue({ message_id: 4 }),
    editMessageText: jest.fn().mockResolvedValue(true),
    answerCbQuery: jest.fn().mockResolvedValue(true),
    deleteMessage: jest.fn().mockResolvedValue(true),

    // Telegram instance (mock)
    telegram: {
      sendMessage: jest.fn().mockResolvedValue({ message_id: 5 }),
      sendPhoto: jest.fn().mockResolvedValue({ message_id: 6 }),
      editMessageText: jest.fn().mockResolvedValue(true),
      deleteMessage: jest.fn().mockResolvedValue(true),
    },

    // Bot info
    botInfo: {
      id: 987654321,
      is_bot: true,
      first_name: 'Test Bot',
      username: 'testbot',
      can_join_groups: true,
      can_read_all_group_messages: false,
      supports_inline_queries: false,
    },

    // Session (will be added by middleware)
    session: {
      state: 'IDLE',
      data: {},
      lastActivity: Date.now(),
    },

    ...overrides,
  } as unknown as Context;

  return mockContext;
}

/**
 * Create mock callback query context
 */
export function createMockCallbackContext(
  data: string,
  overrides: Partial<Context> = {}
): Context {
  const baseContext = createMockContext(overrides);

  return {
    ...baseContext,
    updateType: 'callback_query',
    callbackQuery: {
      id: 'callback_123',
      from: baseContext.from!,
      message: baseContext.message,
      chat_instance: 'chat_instance_123',
      data,
    },
  } as unknown as Context;
}

/**
 * Create mock Telegraf bot
 */
export function createMockBot() {
  return {
    telegram: {
      sendMessage: jest.fn().mockResolvedValue({ message_id: 1 }),
      editMessageText: jest.fn().mockResolvedValue(true),
      deleteMessage: jest.fn().mockResolvedValue(true),
      setWebhook: jest.fn().mockResolvedValue(true),
      deleteWebhook: jest.fn().mockResolvedValue(true),
    },
    launch: jest.fn().mockResolvedValue(undefined),
    stop: jest.fn().mockResolvedValue(undefined),
    use: jest.fn(),
    on: jest.fn(),
    command: jest.fn(),
    action: jest.fn(),
    catch: jest.fn(),
  };
}

/**
 * Assert that context.reply was called with specific text
 */
export function expectReplyWith(context: Context, text: string | RegExp) {
  const replyMock = context.reply as jest.Mock;

  if (typeof text === 'string') {
    expect(replyMock).toHaveBeenCalledWith(
      expect.stringContaining(text),
      expect.anything()
    );
  } else {
    expect(replyMock).toHaveBeenCalledWith(
      expect.stringMatching(text),
      expect.anything()
    );
  }
}

/**
 * Assert that callback query was answered
 */
export function expectCallbackAnswered(context: Context, message?: string) {
  const answerMock = context.answerCbQuery as jest.Mock;

  if (message) {
    expect(answerMock).toHaveBeenCalledWith(expect.stringContaining(message));
  } else {
    expect(answerMock).toHaveBeenCalled();
  }
}
