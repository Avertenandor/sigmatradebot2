/**
 * SigmaTrade Bot - Main Entry Point
 * Initializes database, bot, and all services
 */

import { config } from './config';
import { createLogger } from './utils/logger.util';
import { initializeDatabase, closeDatabase } from './database/data-source';
import { initializeBot, startBot, stopBot } from './bot';
import {
  initializeQueues,
  closeQueues,
  startBlockchainMonitor,
  stopBlockchainMonitor,
  startPaymentProcessor,
  stopPaymentProcessor,
  startRewardCalculator,
  stopRewardCalculator,
  startBackupScheduler,
  stopBackupScheduler,
  startCleanupScheduler,
  stopCleanupScheduler,
} from './jobs';
import {
  startPerformanceReporting,
  stopPerformanceReporting,
  startMemoryMonitoring,
  stopMemoryMonitoring,
} from './utils/performance-monitor.util';

const logger = createLogger('Main');

/**
 * Main application startup
 */
async function main() {
  try {
    // Display startup banner
    console.log(`
╔═══════════════════════════════════════════════════════╗
║           SigmaTrade DeFi Telegram Bot                ║
║              Starting up...                            ║
╚═══════════════════════════════════════════════════════╝
    `);

    logger.info('Starting SigmaTrade Bot', {
      env: config.env,
      nodeVersion: process.version,
    });

    // Step 1: Initialize database
    logger.info('Initializing database...');
    await initializeDatabase();
    logger.info('✅ Database initialized');

    // Step 2: Initialize Bull queues
    logger.info('Initializing background job queues...');
    initializeQueues();
    logger.info('✅ Queues initialized');

    // Step 3: Initialize bot
    logger.info('Initializing Telegram bot...');
    const bot = initializeBot();
    logger.info('✅ Bot initialized');

    // Step 4: Start bot
    logger.info('Starting bot...');
    await startBot(bot);
    logger.info('✅ Bot started successfully');

    // Step 5: Start blockchain monitor
    logger.info('Starting blockchain monitor...');
    await startBlockchainMonitor();
    logger.info('✅ Blockchain monitor started');

    // Step 6: Start payment processor
    logger.info('Starting payment processor...');
    await startPaymentProcessor();
    logger.info('✅ Payment processor started');

    // Step 7: Start reward calculator
    logger.info('Starting reward calculator...');
    await startRewardCalculator();
    logger.info('✅ Reward calculator started');

    // Step 8: Start backup scheduler
    logger.info('Starting backup scheduler...');
    await startBackupScheduler();
    logger.info('✅ Backup scheduler started');

    // Step 9: Start cleanup scheduler
    logger.info('Starting cleanup scheduler...');
    await startCleanupScheduler();
    logger.info('✅ Cleanup scheduler started');

    // Step 10: Start performance monitoring
    logger.info('Starting performance monitoring...');
    startPerformanceReporting(); // Reports performance stats every hour
    startMemoryMonitoring(); // Logs memory usage every 5 minutes
    logger.info('✅ Performance monitoring started');

    console.log(`
╔═══════════════════════════════════════════════════════╗
║        🚀 SigmaTrade Bot is running! 🚀              ║
║                                                       ║
║  Environment: ${config.env.padEnd(40)}║
║  Database: Connected                                  ║
║  Bot: Active                                          ║
║  Blockchain Monitor: Active                           ║
║  Payment Processor: Active                            ║
║  Reward Calculator: Active                            ║
║  Background Jobs: Active                              ║
║  Performance Monitoring: Active                       ║
║                                                       ║
║  Press Ctrl+C to stop                                 ║
╚═══════════════════════════════════════════════════════╝
    `);

    // Setup graceful shutdown
    setupGracefulShutdown(bot);

  } catch (error) {
    logger.error('Fatal error during startup', {
      error: error instanceof Error ? error.message : String(error),
      stack: error instanceof Error ? error.stack : undefined,
    });

    console.error('❌ Failed to start bot:', error);
    process.exit(1);
  }
}

/**
 * Setup graceful shutdown handlers
 */
function setupGracefulShutdown(bot: any) {
  const shutdown = async (signal: string) => {
    console.log(`\n\nReceived ${signal}, starting graceful shutdown...`);

    logger.info(`Received ${signal}, shutting down gracefully...`);

    try {
      // Step 1: Stop background jobs
      logger.info('Stopping blockchain monitor...');
      await stopBlockchainMonitor();
      logger.info('✅ Blockchain monitor stopped');

      logger.info('Stopping payment processor...');
      await stopPaymentProcessor();
      logger.info('✅ Payment processor stopped');

      logger.info('Stopping reward calculator...');
      await stopRewardCalculator();
      logger.info('✅ Reward calculator stopped');

      logger.info('Stopping backup scheduler...');
      await stopBackupScheduler();
      logger.info('✅ Backup scheduler stopped');

      logger.info('Stopping cleanup scheduler...');
      await stopCleanupScheduler();
      logger.info('✅ Cleanup scheduler stopped');

      // Step 2: Stop performance monitoring
      logger.info('Stopping performance monitoring...');
      stopPerformanceReporting();
      stopMemoryMonitoring();
      logger.info('✅ Performance monitoring stopped');

      // Step 3: Stop accepting new updates
      logger.info('Stopping bot...');
      await stopBot(bot);
      logger.info('✅ Bot stopped');

      // Step 4: Close queues
      logger.info('Closing job queues...');
      await closeQueues();
      logger.info('✅ Queues closed');

      // Step 5: Close database connections
      logger.info('Closing database...');
      await closeDatabase();
      logger.info('✅ Database closed');

      console.log(`
╔═══════════════════════════════════════════════════════╗
║      SigmaTrade Bot shut down successfully            ║
╚═══════════════════════════════════════════════════════╝
      `);

      logger.info('Graceful shutdown completed');
      process.exit(0);
    } catch (error) {
      logger.error('Error during shutdown', {
        error: error instanceof Error ? error.message : String(error),
      });

      console.error('❌ Error during shutdown:', error);
      process.exit(1);
    }
  };

  // Handle termination signals
  process.on('SIGTERM', () => shutdown('SIGTERM'));
  process.on('SIGINT', () => shutdown('SIGINT'));

  // Handle uncaught errors
  process.on('uncaughtException', (error) => {
    logger.error('Uncaught exception', {
      error: error.message,
      stack: error.stack,
    });

    console.error('❌ Uncaught exception:', error);

    // Attempt graceful shutdown
    shutdown('uncaughtException');
  });

  process.on('unhandledRejection', (reason) => {
    logger.error('Unhandled rejection', {
      reason: reason instanceof Error ? reason.message : String(reason),
      stack: reason instanceof Error ? reason.stack : undefined,
    });

    console.error('❌ Unhandled rejection:', reason);

    // Attempt graceful shutdown
    shutdown('unhandledRejection');
  });
}

// Start the application
main();
