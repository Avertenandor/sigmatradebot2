/**
 * Wallet Admin Service
 * Manages wallet change requests with approval workflow
 *
 * WORKFLOW:
 * 1. Extended/Super admin creates request (createRequest) → status: pending
 * 2. Super admin approves request (approveRequest) → status: approved
 * 3. Super admin applies request (applyRequest) → status: applied
 *
 * SECURITY:
 * - Only one active request per wallet type (enforced by partial unique index)
 * - Private keys stored in Secret Manager, never in database
 * - All actions audited in financial log
 * - Only super_admin can approve/apply changes
 */

import { AppDataSource } from '../database/data-source';
import { WalletChangeRequest, Admin } from '../database/entities';
import { WalletChangeType } from '../database/entities/WalletChangeRequest.entity';
import { settingsService } from './settings.service';
import { secretStoreService } from './secret-store.service';
import { createLogger } from '../utils/logger.util';
import { logAdminAudit } from '../utils/audit-logger.util';
import { isValidBSCAddress, normalizeWalletAddress } from '../utils/validation.util';
import { config } from '../config';
import { ethers } from 'ethers';

const logger = createLogger('WalletAdminService');

export class WalletAdminService {
  private requestRepo = AppDataSource.getRepository(WalletChangeRequest);
  private adminRepo = AppDataSource.getRepository(Admin);

  /**
   * Create a new wallet change request
   * @param type - Wallet type to change
   * @param newAddress - New wallet address (must be valid BSC address)
   * @param keyOrMnemonic - Private key or mnemonic (required for payout wallet)
   * @param initiatorId - Admin ID who initiates the request
   * @param reason - Optional reason for the change
   */
  async createRequest(
    type: WalletChangeType,
    newAddress: string,
    initiatorId: number,
    keyOrMnemonic?: string,
    reason?: string
  ): Promise<WalletChangeRequest> {
    // Validate initiator
    const initiator = await this.adminRepo.findOne({ where: { id: initiatorId } });
    if (!initiator) {
      throw new Error('Initiator admin not found');
    }

    if (!initiator.canStageWalletChanges) {
      throw new Error('Insufficient permissions. Only Extended Admin and Super Admin can create wallet change requests');
    }

    // Validate address format
    if (!isValidBSCAddress(newAddress)) {
      throw new Error('Invalid BSC address format or checksum');
    }

    // Normalize to EIP-55 checksum format
    const checksummedAddress = normalizeWalletAddress(newAddress);

    // Validate that new address is different from current
    const currentAddress =
      type === 'system_deposit'
        ? await settingsService.getSystemWalletAddress()
        : await settingsService.getPayoutWalletAddress();

    if (checksummedAddress.toLowerCase() === currentAddress.toLowerCase()) {
      throw new Error('New address is the same as current address');
    }

    // Check for existing active request
    const existingRequest = await this.requestRepo.findOne({
      where: {
        type,
        status: 'pending' as any, // TypeORM workaround
      },
    });

    if (existingRequest) {
      throw new Error(`There is already a pending request for ${type}`);
    }

    // For payout wallet: validate and store private key
    let secretRef: string | undefined;

    if (type === 'payout_withdrawal') {
      // SECURITY: Prevent creating payout wallet requests in production without GCP Secret Manager
      if (config.isProduction && !config.gcp.secretManagerEnabled) {
        throw new Error(
          'Cannot create payout wallet requests in production without GCP Secret Manager. ' +
          'Please set GCP_SECRET_MANAGER_ENABLED=true and configure GCP_PROJECT_ID.'
        );
      }

      if (!keyOrMnemonic) {
        throw new Error('Private key or mnemonic is required for payout wallet');
      }

      // Validate that key/mnemonic corresponds to the address
      const derivedAddress = await this.deriveAddressFromKey(keyOrMnemonic);
      if (derivedAddress.toLowerCase() !== checksummedAddress.toLowerCase()) {
        throw new Error('Private key/mnemonic does not match the provided address');
      }

      // Store secret in Secret Manager
      const secretName = `payout-wallet-${Date.now()}-${initiatorId}`;
      secretRef = await secretStoreService.saveSecret(secretName, keyOrMnemonic);

      logger.info('Secret stored in Secret Manager', {
        secretRef,
        secretLength: keyOrMnemonic.length,
      });
    }

    // Create request
    const request = this.requestRepo.create({
      type,
      new_address: checksummedAddress,
      secret_ref: secretRef,
      initiated_by_admin_id: initiatorId,
      status: 'pending',
      reason,
    });

    await this.requestRepo.save(request);

    // Audit log
    await logAdminAudit({
      adminId: initiatorId,
      action: `wallet_change_request_created_${type}`,
      details: {
        requestId: request.id,
        type,
        newAddress: checksummedAddress,
        reason,
        hasSecret: !!secretRef,
      },
    });

    logger.info('Wallet change request created', {
      requestId: request.id,
      type,
      initiator: initiator.displayName,
    });

    return request;
  }

  /**
   * Approve a wallet change request (super_admin only)
   */
  async approveRequest(
    requestId: number,
    approverId: number,
    approvalReason?: string
  ): Promise<WalletChangeRequest> {
    // Validate approver
    const approver = await this.adminRepo.findOne({ where: { id: approverId } });
    if (!approver) {
      throw new Error('Approver admin not found');
    }

    if (!approver.canApproveWalletChanges) {
      throw new Error('Insufficient permissions. Only Super Admin can approve wallet changes');
    }

    // Get request
    const request = await this.requestRepo.findOne({
      where: { id: requestId },
      relations: ['initiated_by'],
    });

    if (!request) {
      throw new Error('Request not found');
    }

    if (request.status !== 'pending') {
      throw new Error(`Cannot approve request with status: ${request.status}`);
    }

    // Update request
    request.status = 'approved';
    request.approved_by_admin_id = approverId;
    request.approved_at = new Date();
    if (approvalReason) {
      request.reason = `${request.reason || ''}\nApproval: ${approvalReason}`.trim();
    }

    await this.requestRepo.save(request);

    // Audit log
    await logAdminAudit({
      adminId: approverId,
      action: `wallet_change_request_approved_${request.type}`,
      details: {
        requestId: request.id,
        type: request.type,
        newAddress: request.new_address,
        initiatedBy: request.initiated_by.displayName,
        reason: approvalReason,
      },
    });

    logger.info('Wallet change request approved', {
      requestId: request.id,
      type: request.type,
      approver: approver.displayName,
    });

    return request;
  }

  /**
   * Reject a wallet change request (super_admin only)
   */
  async rejectRequest(
    requestId: number,
    rejectorId: number,
    rejectionReason: string
  ): Promise<WalletChangeRequest> {
    // Validate rejector
    const rejector = await this.adminRepo.findOne({ where: { id: rejectorId } });
    if (!rejector) {
      throw new Error('Rejector admin not found');
    }

    if (!rejector.canApproveWalletChanges) {
      throw new Error('Insufficient permissions. Only Super Admin can reject wallet changes');
    }

    // Get request
    const request = await this.requestRepo.findOne({
      where: { id: requestId },
      relations: ['initiated_by'],
    });

    if (!request) {
      throw new Error('Request not found');
    }

    if (request.status !== 'pending' && request.status !== 'approved') {
      throw new Error(`Cannot reject request with status: ${request.status}`);
    }

    // Update request
    request.status = 'rejected';
    request.reason = `${request.reason || ''}\nRejection: ${rejectionReason}`.trim();

    await this.requestRepo.save(request);

    // Cleanup secret if exists
    if (request.secret_ref) {
      try {
        await secretStoreService.deleteSecret(request.secret_ref);
        logger.info('Secret deleted after rejection', { secretRef: request.secret_ref });
      } catch (error) {
        logger.error('Failed to delete secret after rejection', { error, secretRef: request.secret_ref });
      }
    }

    // Audit log
    await logAdminAudit({
      adminId: rejectorId,
      action: `wallet_change_request_rejected_${request.type}`,
      details: {
        requestId: request.id,
        type: request.type,
        newAddress: request.new_address,
        initiatedBy: request.initiated_by.displayName,
        reason: rejectionReason,
      },
    });

    logger.info('Wallet change request rejected', {
      requestId: request.id,
      type: request.type,
      rejector: rejector.displayName,
    });

    return request;
  }

  /**
   * Apply an approved wallet change request (super_admin only)
   * This actually changes the wallet addresses in system settings
   */
  async applyRequest(requestId: number, applierId: number): Promise<WalletChangeRequest> {
    // Validate applier
    const applier = await this.adminRepo.findOne({ where: { id: applierId } });
    if (!applier) {
      throw new Error('Applier admin not found');
    }

    if (!applier.canApproveWalletChanges) {
      throw new Error('Insufficient permissions. Only Super Admin can apply wallet changes');
    }

    // Get request
    const request = await this.requestRepo.findOne({
      where: { id: requestId },
      relations: ['initiated_by', 'approved_by'],
    });

    if (!request) {
      throw new Error('Request not found');
    }

    if (request.status !== 'approved') {
      throw new Error(`Cannot apply request with status: ${request.status}. Must be approved first.`);
    }

    // Apply the change based on type
    if (request.type === 'system_deposit') {
      await this.applySystemDepositWalletChange(request);
    } else if (request.type === 'payout_withdrawal') {
      await this.applyPayoutWalletChange(request);
    }

    // Update request status
    request.status = 'applied';
    request.applied_at = new Date();
    await this.requestRepo.save(request);

    // Increment wallets version
    await settingsService.incrementWalletsVersion();

    // Audit log
    await logAdminAudit({
      adminId: applierId,
      action: `wallet_change_applied_${request.type}`,
      details: {
        requestId: request.id,
        type: request.type,
        newAddress: request.new_address,
        initiatedBy: request.initiated_by?.displayName,
        approvedBy: request.approved_by?.displayName,
      },
    });

    logger.info('✅ Wallet change applied successfully', {
      requestId: request.id,
      type: request.type,
      applier: applier.displayName,
    });

    return request;
  }

  /**
   * Get all requests (with filters)
   */
  async getRequests(filters?: {
    type?: WalletChangeType;
    status?: string;
    limit?: number;
  }): Promise<WalletChangeRequest[]> {
    const query: any = {};

    if (filters?.type) {
      query.type = filters.type;
    }

    if (filters?.status) {
      query.status = filters.status;
    }

    return await this.requestRepo.find({
      where: query,
      relations: ['initiated_by', 'approved_by'],
      order: { created_at: 'DESC' },
      take: filters?.limit || 50,
    });
  }

  /**
   * Get a specific request by ID
   */
  async getRequest(requestId: number): Promise<WalletChangeRequest | null> {
    return await this.requestRepo.findOne({
      where: { id: requestId },
      relations: ['initiated_by', 'approved_by'],
    });
  }

  // ==================== PRIVATE METHODS ====================

  /**
   * Apply system deposit wallet change
   */
  private async applySystemDepositWalletChange(request: WalletChangeRequest): Promise<void> {
    const oldAddress = await settingsService.getSystemWalletAddress();

    // Update system settings
    await settingsService.setSystemWalletAddress(request.new_address);

    // Reload blockchain event monitor with new address
    const { blockchainService } = await import('./blockchain');
    await blockchainService.reloadSystemWalletAddress(request.new_address);

    logger.info('System deposit wallet changed', {
      oldAddress,
      newAddress: request.new_address,
    });
  }

  /**
   * Apply payout wallet change
   */
  private async applyPayoutWalletChange(request: WalletChangeRequest): Promise<void> {
    if (!request.secret_ref) {
      throw new Error('Secret reference is missing for payout wallet');
    }

    // Update system settings
    await settingsService.setPayoutWalletAddress(request.new_address);

    // Reload provider manager with new signer
    const { blockchainService } = await import('./blockchain');
    await blockchainService.reloadPayoutWallet(request.secret_ref);

    logger.info('Payout wallet changed', {
      newAddress: request.new_address,
      secretRef: request.secret_ref,
    });
  }

  /**
   * Derive address from private key or mnemonic
   */
  private async deriveAddressFromKey(keyOrMnemonic: string): Promise<string> {
    try {
      // Try as private key first
      if (keyOrMnemonic.startsWith('0x') && keyOrMnemonic.length === 66) {
        const wallet = new ethers.Wallet(keyOrMnemonic);
        return wallet.address;
      }

      // Try as mnemonic (12 or 24 words)
      const words = keyOrMnemonic.trim().split(/\s+/);
      if (words.length === 12 || words.length === 24) {
        const wallet = ethers.Wallet.fromPhrase(keyOrMnemonic);
        return wallet.address;
      }

      throw new Error('Invalid format. Must be a private key (0x...) or mnemonic phrase (12/24 words)');
    } catch (error) {
      logger.error('Failed to derive address from key', { error });
      throw new Error('Invalid private key or mnemonic format');
    }
  }
}

export const walletAdminService = new WalletAdminService();
export default walletAdminService;
