/**
 * Contract interaction utilities for the Flashix arbitrage system.
 *
 * This module provides a clean, high-level API for interacting with all three
 * deployed smart contracts (LendingPool, ArbitrageExecutor, SignalValidator)
 * without requiring direct ABI calls.
 */

const fs = require('fs');
const path = require('path');
const { ethers } = require('ethers');

class ContractInteractionError extends Error {
  constructor(message) {
    super(message);
    this.name = 'ContractInteractionError';
  }
}

class ContractNotDeployedError extends ContractInteractionError {
  constructor(message) {
    super(message);
    this.name = 'ContractNotDeployedError';
  }
}

class ContractManager {
  /**
   * Initialize contract manager.
   * @param {ethers.Provider} provider - Ethers provider for RPC communication
   * @param {ethers.Signer} signer - Optional signer for sending transactions
   * @param {string} network - Network name ("zgTestnet" or "zgMainnet")
   */
  constructor(provider, signer = null, network = 'zgTestnet') {
    this.provider = provider;
    this.signer = signer;
    this.network = network;

    this._lendingPool = null;
    this._arbitrageExecutor = null;
    this._signalValidator = null;

    this._loadDeployments();
  }

  /**
   * Load contract addresses and ABIs from deployment artifacts.
   */
  _loadDeployments() {
    // Try to load from deployments file first
    const deploymentsPath = path.join(
      __dirname,
      '..',
      'contracts',
      'deployments',
      'testnet.json'
    );

    if (fs.existsSync(deploymentsPath)) {
      const deployments = JSON.parse(fs.readFileSync(deploymentsPath, 'utf-8'));
      const contracts = deployments.contracts || {};
      this.lendingPoolAddress = contracts.LendingPool?.address;
      this.arbitrageExecutorAddress = contracts.ArbitrageExecutor?.address;
      this.signalValidatorAddress = contracts.SignalValidator?.address;
    } else {
      // Try to load from environment variables
      this.lendingPoolAddress = process.env.LENDING_POOL_ADDRESS;
      this.arbitrageExecutorAddress = process.env.ARBITRAGE_EXECUTOR_ADDRESS;
      this.signalValidatorAddress = process.env.SIGNAL_VALIDATOR_ADDRESS;
    }

    console.log(`Loaded contract addresses from ${this.network}:`);
    console.log(`  LendingPool: ${this.lendingPoolAddress}`);
    console.log(`  ArbitrageExecutor: ${this.arbitrageExecutorAddress}`);
    console.log(`  SignalValidator: ${this.signalValidatorAddress}`);
  }

  /**
   * Load ABI from JSON file.
   * @param {string} contractName - Contract name
   * @returns {Array} Contract ABI
   */
  _loadAbi(contractName) {
    const abiPath = path.join(
      __dirname,
      '..',
      'contracts',
      'abi',
      `${contractName}.json`
    );

    if (!fs.existsSync(abiPath)) {
      throw new ContractNotDeployedError(
        `ABI not found for ${contractName} at ${abiPath}`
      );
    }

    const data = JSON.parse(fs.readFileSync(abiPath, 'utf-8'));
    return data.abi || [];
  }

  /**
   * Get initialized LendingPool contract instance.
   * @returns {ethers.Contract} LendingPool contract
   */
  getLendingPool() {
    if (!this._lendingPool) {
      if (!this.lendingPoolAddress) {
        throw new ContractNotDeployedError('LENDING_POOL_ADDRESS not configured');
      }

      const abi = this._loadAbi('LendingPool');
      this._lendingPool = new ethers.Contract(
        this.lendingPoolAddress,
        abi,
        this.signer || this.provider
      );
    }

    return this._lendingPool;
  }

  /**
   * Get initialized ArbitrageExecutor contract instance.
   * @returns {ethers.Contract} ArbitrageExecutor contract
   */
  getArbitrageExecutor() {
    if (!this._arbitrageExecutor) {
      if (!this.arbitrageExecutorAddress) {
        throw new ContractNotDeployedError('ARBITRAGE_EXECUTOR_ADDRESS not configured');
      }

      const abi = this._loadAbi('ArbitrageExecutor');
      this._arbitrageExecutor = new ethers.Contract(
        this.arbitrageExecutorAddress,
        abi,
        this.signer || this.provider
      );
    }

    return this._arbitrageExecutor;
  }

  /**
   * Get initialized SignalValidator contract instance.
   * @returns {ethers.Contract} SignalValidator contract
   */
  getSignalValidator() {
    if (!this._signalValidator) {
      if (!this.signalValidatorAddress) {
        throw new ContractNotDeployedError('SIGNAL_VALIDATOR_ADDRESS not configured');
      }

      const abi = this._loadAbi('SignalValidator');
      this._signalValidator = new ethers.Contract(
        this.signalValidatorAddress,
        abi,
        this.signer || this.provider
      );
    }

    return this._signalValidator;
  }

  /**
   * Get maximum flashloan available for a token.
   * @param {string} tokenAddress - ERC-20 token address
   * @returns {Promise<BigInt>} Maximum flashloan amount
   */
  async getMaxFlashloan(tokenAddress) {
    try {
      const lendingPool = this.getLendingPool();
      const maxLoan = await lendingPool.maxFlashLoan(tokenAddress);
      return maxLoan;
    } catch (error) {
      throw new ContractInteractionError(`Failed to get max flashloan: ${error.message}`);
    }
  }

  /**
   * Get flashloan fee for a given amount.
   * @param {string} tokenAddress - ERC-20 token address
   * @param {BigInt|number} amount - Loan amount in token units
   * @returns {Promise<BigInt>} Fee amount in token units
   */
  async getCurrentFee(tokenAddress, amount) {
    try {
      const lendingPool = this.getLendingPool();
      const fee = await lendingPool.flashFee(tokenAddress, amount);
      return fee;
    } catch (error) {
      throw new ContractInteractionError(`Failed to get flashloan fee: ${error.message}`);
    }
  }

  /**
   * Execute a flashloan transaction.
   * @param {string} tokenAddress - ERC-20 token to borrow
   * @param {BigInt|number} amount - Amount to borrow in token units
   * @param {string} signalData - Encoded arbitrage signal (hex string)
   * @param {Object} overrides - Optional transaction overrides {gasLimit, gasPrice}
   * @returns {Promise<ethers.TransactionResponse>} Transaction response
   */
  async executeFlashloan(tokenAddress, amount, signalData, overrides = {}) {
    try {
      if (!this.signer) {
        throw new ContractInteractionError('No signer configured for sending transactions');
      }

      const lendingPool = this.getLendingPool().connect(this.signer);
      const arbitrageExecutor = this.getArbitrageExecutor();

      const tx = await lendingPool.flashLoan(
        arbitrageExecutor.getAddress(),
        tokenAddress,
        amount,
        signalData,
        {
          ...overrides,
          // Auto-estimate gas if not provided
          gasLimit: overrides.gasLimit || (await lendingPool.flashLoan.estimateGas(
            arbitrageExecutor.getAddress(),
            tokenAddress,
            amount,
            signalData
          )),
        }
      );

      console.log(`Flashloan transaction submitted: ${tx.hash}`);
      return tx;
    } catch (error) {
      throw new ContractInteractionError(`Failed to execute flashloan: ${error.message}`);
    }
  }

  /**
   * Wait for transaction confirmation.
   * @param {string} txHash - Transaction hash
   * @param {number} confirmations - Number of confirmations to wait for
   * @returns {Promise<ethers.TransactionReceipt>} Transaction receipt
   */
  async waitForConfirmation(txHash, confirmations = 2) {
    try {
      const receipt = await this.provider.waitForTransaction(txHash, confirmations);

      if (receipt.status === 1) {
        console.log(`Transaction confirmed: ${txHash}`);
        return receipt;
      } else {
        throw new ContractInteractionError(`Transaction failed: ${txHash}`);
      }
    } catch (error) {
      throw new ContractInteractionError(`Failed to wait for confirmation: ${error.message}`);
    }
  }

  /**
   * Get accumulated fees for a token in the lending pool.
   * @param {string} tokenAddress - ERC-20 token address
   * @returns {Promise<BigInt>} Accumulated fees in token units
   */
  async getAccumulatedFees(tokenAddress) {
    try {
      const lendingPool = this.getLendingPool();
      const fees = await lendingPool.getAccumulatedFees(tokenAddress);
      return fees;
    } catch (error) {
      throw new ContractInteractionError(`Failed to get accumulated fees: ${error.message}`);
    }
  }

  /**
   * Get total number of arbitrage executions.
   * @returns {Promise<BigInt>} Number of successful executions
   */
  async getExecutionCount() {
    try {
      const executor = this.getArbitrageExecutor();
      const count = await executor.getExecutionCount();
      return count;
    } catch (error) {
      throw new ContractInteractionError(`Failed to get execution count: ${error.message}`);
    }
  }

  /**
   * Verify a signal through SignalValidator.
   * @param {Object} signal - Arbitrage signal object
   * @returns {Promise<boolean>} True if signal is valid
   */
  async verifySignal(signal) {
    try {
      const validator = this.getSignalValidator();
      const result = await validator.verify(signal);
      return result;
    } catch (error) {
      throw new ContractInteractionError(`Signal verification failed: ${error.message}`);
    }
  }

  /**
   * Test connectivity to all contracts.
   * @returns {Promise<Object>} Object with contract names and connectivity status
   */
  async testContractConnectivity() {
    const results = {};

    const contracts = [
      { name: 'LendingPool', getter: () => this.getLendingPool() },
      { name: 'ArbitrageExecutor', getter: () => this.getArbitrageExecutor() },
      { name: 'SignalValidator', getter: () => this.getSignalValidator() },
    ];

    for (const { name, getter } of contracts) {
      try {
        const contract = getter();

        // Try a simple read call
        if (name === 'LendingPool') {
          await contract.FEE_BPS();
        } else if (name === 'SignalValidator') {
          await contract.getTrustedSigner();
        } else if (name === 'ArbitrageExecutor') {
          await contract.getExecutionCount();
        }

        results[name] = true;
        console.log(`✓ ${name} responsive`);
      } catch (error) {
        results[name] = false;
        console.error(`✗ ${name} not responsive: ${error.message}`);
      }
    }

    return results;
  }
}

/**
 * Initialize contract manager with ethers provider.
 * @param {string} rpcUrl - 0G Chain RPC endpoint URL
 * @param {ethers.Signer} signer - Optional signer for transactions
 * @param {string} network - Network name
 * @returns {Promise<ContractManager>} Initialized ContractManager
 */
async function initializeContracts(rpcUrl, signer = null, network = 'zgTestnet') {
  try {
    const provider = new ethers.JsonRpcProvider(rpcUrl);

    // Test connection
    await provider.getNetwork();

    console.log(`Connected to ${network} at ${rpcUrl}`);
    return new ContractManager(provider, signer, network);
  } catch (error) {
    throw new ContractInteractionError(`Failed to initialize contracts: ${error.message}`);
  }
}

module.exports = {
  ContractManager,
  ContractInteractionError,
  ContractNotDeployedError,
  initializeContracts,
};
