/**
 * Sanitized Backup Configuration
 *
 * P0 SECURITY FIX: Prevents sensitive data from being committed to git
 *
 * Only whitelisted tables are backed up (no secrets/keys/config):
 * - users: User accounts and wallet addresses
 * - deposits: Deposit records and levels
 * - transactions: Transaction history
 * - referrals: Referral relationships
 * - referral_earnings: Referral payouts
 * - admins: Admin user records
 *
 * Excluded from backup (security):
 * - config/environment tables (may contain secrets)
 * - session tables (contain auth tokens)
 * - retry tables (may contain sensitive operation details)
 * - notification tables (may contain personal messages)
 *
 * Schedule: Every 6 hours (cron: "0 *\/6 * * *")
 * Format: pg_dump --format=custom --compress=9 (fast restore)
 * Storage: Git branch 'backups/sanitized' (separate from code)
 * Retention: 90 days
 */

export interface SanitizedBackupConfig {
  enabled: boolean;
  cron: string;                   // "0 */6 * * *" = every 6 hours
  dir: string;                    // "./backups/daily"
  retentionDays: number;          // 90 days
  gitRemote: string;              // "origin"
  gitBranch: string;              // "backups/sanitized"
  tables: string[];               // whitelist of safe tables
}

export const sanitizedBackupConfig: SanitizedBackupConfig = {
  enabled: process.env.BACKUP_ENABLED !== 'false',
  cron: process.env.BACKUP_CRON || '0 */6 * * *',  // Every 6 hours at :00
  dir: process.env.BACKUP_DIR || './backups/daily',
  retentionDays: Number(process.env.BACKUP_RETENTION_DAYS || 90),
  gitRemote: process.env.BACKUP_GIT_REMOTE || 'origin',
  gitBranch: process.env.BACKUP_GIT_BRANCH || 'backups/sanitized',
  tables: (
    process.env.BACKUP_TABLES ||
    'users,deposits,transactions,referrals,referral_earnings,admins'
  )
    .split(',')
    .map(s => s.trim())
    .filter(Boolean),
};
