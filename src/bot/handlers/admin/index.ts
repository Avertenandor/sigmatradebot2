/**
 * Admin Handlers Index
 * Exports all admin handler functions
 */

// Panel and Statistics
export {
  handleAdminPanel,
  handleAdminStats,
} from './panel.handler';

// Broadcasting and User Messages
export {
  handleStartBroadcast,
  handleBroadcastMessage,
  handleBroadcastStatus,
  handleStartSendToUser,
  handleSendToUserMessage,
} from './broadcast.handler';

// User Management (Ban/Unban)
export {
  handleStartBanUser,
  handleBanUserInput,
  handleStartUnbanUser,
  handleUnbanUserInput,
} from './users.handler';

// Admin Management
export {
  handleStartPromoteAdmin,
  handlePromoteAdminInput,
  handleListAdmins,
  handleRemoveAdmin,
  handleRegenerateMasterKey,
} from './management.handler';

// Withdrawal Management
export {
  handlePendingWithdrawals,
  handleApproveWithdrawal,
  handleRejectWithdrawal,
} from './withdrawals.handler';

// Financial Password Recovery
export {
  handleFinpassList,
  handleFinpassView,
  handleFinpassApprove,
  handleFinpassReject,
} from './finpass-recovery.handler';

// Deposit Settings
export {
  handleDepositSettings,
  handleSetMaxLevel,
  handleRoiStats,
} from './deposit-settings.handler';

// Blacklist Management (Pre-registration Ban)
export {
  handleBlacklistMenu,
  handleStartBlacklistAdd,
  handleBlacklistAddInput,
  handleStartBlacklistRemove,
  handleBlacklistRemoveInput,
} from './blacklist.handler';

// Import for default export
import * as panelHandler from './panel.handler';
import * as broadcastHandler from './broadcast.handler';
import * as usersHandler from './users.handler';
import * as managementHandler from './management.handler';
import * as withdrawalsHandler from './withdrawals.handler';
import * as depositSettingsHandler from './deposit-settings.handler';

// Default export for backward compatibility
export default {
  handleAdminPanel: panelHandler.handleAdminPanel,
  handleAdminStats: panelHandler.handleAdminStats,
  handleStartBroadcast: broadcastHandler.handleStartBroadcast,
  handleBroadcastMessage: broadcastHandler.handleBroadcastMessage,
  handleBroadcastStatus: broadcastHandler.handleBroadcastStatus,
  handleStartSendToUser: broadcastHandler.handleStartSendToUser,
  handleSendToUserMessage: broadcastHandler.handleSendToUserMessage,
  handleStartBanUser: usersHandler.handleStartBanUser,
  handleBanUserInput: usersHandler.handleBanUserInput,
  handleStartUnbanUser: usersHandler.handleStartUnbanUser,
  handleUnbanUserInput: usersHandler.handleUnbanUserInput,
  handleStartPromoteAdmin: managementHandler.handleStartPromoteAdmin,
  handlePromoteAdminInput: managementHandler.handlePromoteAdminInput,
  handlePendingWithdrawals: withdrawalsHandler.handlePendingWithdrawals,
  handleApproveWithdrawal: withdrawalsHandler.handleApproveWithdrawal,
  handleRejectWithdrawal: withdrawalsHandler.handleRejectWithdrawal,
  handleListAdmins: managementHandler.handleListAdmins,
  handleRemoveAdmin: managementHandler.handleRemoveAdmin,
  handleRegenerateMasterKey: managementHandler.handleRegenerateMasterKey,
  handleDepositSettings: depositSettingsHandler.handleDepositSettings,
  handleSetMaxLevel: depositSettingsHandler.handleSetMaxLevel,
  handleRoiStats: depositSettingsHandler.handleRoiStats,
};
