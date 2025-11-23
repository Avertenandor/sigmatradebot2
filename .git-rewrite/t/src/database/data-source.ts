/**
 * TypeORM Data Source Configuration
 * Main database connection configuration
 */

import { DataSource } from 'typeorm';
import { config } from '../config';
import path from 'path';

export const AppDataSource = new DataSource({
  type: 'postgres',
  host: config.database.host,
  port: config.database.port,
  username: config.database.username,
  password: config.database.password,
  database: config.database.database,
  synchronize: config.database.synchronize, // NEVER true in production!
  logging: config.database.logging,
  entities: [path.join(__dirname, '/entities/**/*.entity{.ts,.js}')],
  migrations: [path.join(__dirname, '/migrations/**/*{.ts,.js}')],
  subscribers: [],
  maxQueryExecutionTime: 10000, // Log queries taking longer than 10s
  extra: {
    // Connection pool configuration
    max: 20, // Maximum number of clients in the pool
    min: 5, // Minimum number of clients in the pool
    idleTimeoutMillis: 30000, // Close idle clients after 30s
    connectionTimeoutMillis: 2000, // Return an error if connection not established in 2s
  },
});

/**
 * Initialize database connection
 */
export const initializeDatabase = async (): Promise<void> => {
  try {
    await AppDataSource.initialize();
    console.log('✅ Database connection initialized successfully');

    // Run migrations automatically (optional - can be disabled for manual control)
    if (config.isProduction) {
      await AppDataSource.runMigrations();
      console.log('✅ Database migrations completed');
    }
  } catch (error) {
    console.error('❌ Error initializing database:', error);
    throw error;
  }
};

/**
 * Close database connection gracefully
 */
export const closeDatabase = async (): Promise<void> => {
  if (AppDataSource.isInitialized) {
    await AppDataSource.destroy();
    console.log('✅ Database connection closed');
  }
};

export default AppDataSource;
