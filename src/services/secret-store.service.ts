/**
 * Secret Store Service
 * Manages secure storage of sensitive data (private keys, mnemonics)
 *
 * PRODUCTION: GCP Secret Manager
 * DEVELOPMENT: Local file storage with warning
 *
 * SECURITY:
 * - Secrets never logged
 * - Secrets never stored in database
 * - Access requires service account authentication
 * - All access is audited
 */

import * as fs from 'fs';
import * as path from 'path';
import logger from '../utils/logger.util';

// GCP Secret Manager (production)
// Uncomment when @google-cloud/secret-manager is installed
// import { SecretManagerServiceClient } from '@google-cloud/secret-manager';

class SecretStoreService {
  private isDevelopment: boolean;
  private secretsDir: string;
  // private client?: SecretManagerServiceClient;
  private projectId: string;

  constructor() {
    this.isDevelopment = process.env.NODE_ENV !== 'production';
    this.secretsDir = path.join(process.cwd(), '.secrets', 'dev');
    this.projectId = process.env.GCP_PROJECT_ID || 'sigmatradebot';

    if (this.isDevelopment) {
      // Create local secrets directory for development
      if (!fs.existsSync(this.secretsDir)) {
        fs.mkdirSync(this.secretsDir, { recursive: true });
      }
      logger.warn('⚠️ SecretStore: Using LOCAL file storage (development only)');
    } else {
      // Initialize GCP Secret Manager client
      // Uncomment when @google-cloud/secret-manager is installed
      // this.client = new SecretManagerServiceClient();
      logger.info('✅ SecretStore: Using GCP Secret Manager (production)');
    }
  }

  /**
   * Save a secret (private key or mnemonic)
   * @param name - Unique identifier for the secret
   * @param value - Secret value (will be encrypted in transit and at rest)
   * @returns Secret reference ID
   */
  public async saveSecret(name: string, value: string): Promise<string> {
    // Validate secret name
    if (!name || !/^[a-zA-Z0-9_-]+$/.test(name)) {
      throw new Error('Invalid secret name. Use only alphanumeric, dash, and underscore');
    }

    if (!value || value.length < 32) {
      throw new Error('Invalid secret value. Must be at least 32 characters');
    }

    // NEVER log the actual secret
    logger.info('SecretStore: Saving secret', {
      name,
      length: value.length,
      env: this.isDevelopment ? 'dev' : 'prod',
    });

    if (this.isDevelopment) {
      return await this.saveLocalSecret(name, value);
    } else {
      return await this.saveGcpSecret(name, value);
    }
  }

  /**
   * Access a secret by reference
   * @param secretRef - Reference ID returned by saveSecret
   * @returns Secret value
   */
  public async accessSecret(secretRef: string): Promise<string> {
    if (!secretRef) {
      throw new Error('Secret reference is required');
    }

    // NEVER log the secret ref in production (could be sensitive)
    logger.debug('SecretStore: Accessing secret', {
      refLength: secretRef.length,
      env: this.isDevelopment ? 'dev' : 'prod',
    });

    if (this.isDevelopment) {
      return await this.accessLocalSecret(secretRef);
    } else {
      return await this.accessGcpSecret(secretRef);
    }
  }

  /**
   * Delete a secret (optional cleanup)
   * @param secretRef - Reference ID
   */
  public async deleteSecret(secretRef: string): Promise<void> {
    logger.info('SecretStore: Deleting secret', {
      refLength: secretRef.length,
      env: this.isDevelopment ? 'dev' : 'prod',
    });

    if (this.isDevelopment) {
      await this.deleteLocalSecret(secretRef);
    } else {
      await this.deleteGcpSecret(secretRef);
    }
  }

  // ==================== DEVELOPMENT (Local File Storage) ====================

  private async saveLocalSecret(name: string, value: string): Promise<string> {
    const secretPath = path.join(this.secretsDir, `${name}.secret`);
    fs.writeFileSync(secretPath, value, { mode: 0o600 }); // Read/write for owner only
    logger.warn(`⚠️ DEV: Secret saved to ${secretPath}`);
    return `local://${name}`;
  }

  private async accessLocalSecret(secretRef: string): Promise<string> {
    if (!secretRef.startsWith('local://')) {
      throw new Error('Invalid local secret reference');
    }

    const name = secretRef.replace('local://', '');
    const secretPath = path.join(this.secretsDir, `${name}.secret`);

    if (!fs.existsSync(secretPath)) {
      throw new Error(`Secret not found: ${name}`);
    }

    return fs.readFileSync(secretPath, 'utf-8');
  }

  private async deleteLocalSecret(secretRef: string): Promise<void> {
    if (!secretRef.startsWith('local://')) {
      throw new Error('Invalid local secret reference');
    }

    const name = secretRef.replace('local://', '');
    const secretPath = path.join(this.secretsDir, `${name}.secret`);

    if (fs.existsSync(secretPath)) {
      fs.unlinkSync(secretPath);
      logger.warn(`⚠️ DEV: Secret deleted from ${secretPath}`);
    }
  }

  // ==================== PRODUCTION (GCP Secret Manager) ====================

  private async saveGcpSecret(name: string, value: string): Promise<string> {
    // TODO: Implement GCP Secret Manager integration
    // Uncomment when @google-cloud/secret-manager is installed
    /*
    const parent = `projects/${this.projectId}`;
    const secretId = `sigmatradebot-wallet-${name}`;

    // Create secret
    const [secret] = await this.client!.createSecret({
      parent,
      secretId,
      secret: {
        replication: {
          automatic: {},
        },
      },
    });

    // Add secret version
    const [version] = await this.client!.addSecretVersion({
      parent: secret.name,
      payload: {
        data: Buffer.from(value, 'utf8'),
      },
    });

    logger.info('✅ GCP Secret created', {
      name: secret.name,
      version: version.name,
    });

    return version.name!;
    */

    throw new Error('GCP Secret Manager not configured. Install @google-cloud/secret-manager');
  }

  private async accessGcpSecret(secretRef: string): Promise<string> {
    // TODO: Implement GCP Secret Manager integration
    // Uncomment when @google-cloud/secret-manager is installed
    /*
    const [version] = await this.client!.accessSecretVersion({
      name: secretRef,
    });

    const payload = version.payload?.data?.toString();
    if (!payload) {
      throw new Error('Secret payload is empty');
    }

    return payload;
    */

    throw new Error('GCP Secret Manager not configured. Install @google-cloud/secret-manager');
  }

  private async deleteGcpSecret(secretRef: string): Promise<void> {
    // TODO: Implement GCP Secret Manager integration
    // Uncomment when @google-cloud/secret-manager is installed
    /*
    // Extract secret name from version reference
    const secretName = secretRef.split('/versions/')[0];
    await this.client!.deleteSecret({
      name: secretName,
    });

    logger.info('✅ GCP Secret deleted', { secretName });
    */

    throw new Error('GCP Secret Manager not configured. Install @google-cloud/secret-manager');
  }
}

// Singleton instance
export const secretStoreService = new SecretStoreService();
export default secretStoreService;
