import { expect } from "chai";
import { ethers } from "hardhat";
import { Contract, Signer } from "ethers";

function encodeSignal(signal: any): string {
  return ethers.AbiCoder.defaultAbiCoder().encode(
    ["tuple(bytes32,address,address,address,uint256,uint256,uint256,uint8,bytes32,bytes32)"],
    [[
      signal.opportunityId,
      signal.dexA,
      signal.dexB,
      signal.borrowToken,
      signal.borrowAmount,
      signal.minProfit,
      signal.deadline,
      signal.signatureV,
      signal.signatureR,
      signal.signatureS,
    ]]
  );
}

describe("ArbitrageExecutor", () => {
  let arbitrageExecutor: Contract;
  let lendingPool: Contract;
  let signalValidator: Contract;
  let usdc: Contract;
  let dexA: Contract;
  let dexB: Contract;
  let owner: Signer;
  let teeAccount: Signer;
  let profitRecipient: Signer;
  let other: Signer;
  let ownerAddr: string;
  let teeAddr: string;
  let profitRecipientAddr: string;
  let otherAddr: string;

  const INITIAL_BALANCE = ethers.parseUnits("1000000", 6);
  const LOAN_AMOUNT = ethers.parseUnits("10000", 6);

  before(async () => {
    [owner, teeAccount, profitRecipient, other] = await ethers.getSigners();
    ownerAddr = await owner.getAddress();
    teeAddr = await teeAccount.getAddress();
    profitRecipientAddr = await profitRecipient.getAddress();
    otherAddr = await other.getAddress();

    // Deploy mock tokens
    const MockUSDC = await ethers.getContractFactory("MockUSDC");
    usdc = await MockUSDC.deploy();

    // Deploy mock DEX routers
    const MockDEXRouter = await ethers.getContractFactory("MockDEXRouter");
    dexA = await MockDEXRouter.deploy();
    dexB = await MockDEXRouter.deploy();

    // Deploy lending pool
    const LendingPool = await ethers.getContractFactory("LendingPool");
    lendingPool = await LendingPool.deploy();

    // Set up tokens in lending pool
    const usdcAddr = await usdc.getAddress();
    await lendingPool.setTokenListing(usdcAddr, true);

    // Fund lending pool
    await usdc.transfer(await lendingPool.getAddress(), INITIAL_BALANCE);

    // Deploy signal validator
    const SignalValidator = await ethers.getContractFactory("SignalValidator");
    signalValidator = await SignalValidator.deploy(teeAddr);

    // Deploy arbitrage executor
    const ArbitrageExecutor = await ethers.getContractFactory("ArbitrageExecutor");
    arbitrageExecutor = await ArbitrageExecutor.deploy(profitRecipientAddr);

    // Wire up contracts
    await arbitrageExecutor.setLendingPool(await lendingPool.getAddress());
    await arbitrageExecutor.setSignalValidator(await signalValidator.getAddress());

    // Approve DEX routers
    await arbitrageExecutor.setRouterApproval(await dexA.getAddress(), true);
    await arbitrageExecutor.setRouterApproval(await dexB.getAddress(), true);

    // Fund executor with tokens for callbacks
    await usdc.transfer(await arbitrageExecutor.getAddress(), INITIAL_BALANCE);

    // Set up DEX exchange rates
    await dexA.setExchangeRate(usdcAddr, usdcAddr, ethers.parseUnits("1", 18)); // 1:1
    await dexB.setExchangeRate(usdcAddr, usdcAddr, ethers.parseUnits("1", 18));
  });

  describe("Deployment", () => {
    it("should deploy with correct owner", async () => {
      expect(await arbitrageExecutor.owner()).to.equal(ownerAddr);
    });

    it("should set profit recipient on deployment", async () => {
      expect(await arbitrageExecutor.profitRecipient()).to.equal(profitRecipientAddr);
    });

    it("should initialize execution counter to 0", async () => {
      expect(await arbitrageExecutor.getExecutionCount()).to.equal(0);
    });
  });

  describe("Contract Configuration", () => {
    it("should allow owner to set lending pool", async () => {
      const newLendingPool = ethers.getAddress("0x5555555555555555555555555555555555555555");
      await expect(arbitrageExecutor.setLendingPool(newLendingPool))
        .to.emit(arbitrageExecutor, "LendingPoolUpdated")
        .withArgs(newLendingPool);

      // Reset for subsequent tests
      await arbitrageExecutor.setLendingPool(await lendingPool.getAddress());
    });

    it("should allow owner to set signal validator", async () => {
      const newValidator = ethers.getAddress("0x6666666666666666666666666666666666666666");
      await expect(arbitrageExecutor.setSignalValidator(newValidator))
        .to.emit(arbitrageExecutor, "SignalValidatorUpdated")
        .withArgs(newValidator);

      // Reset for subsequent tests
      await arbitrageExecutor.setSignalValidator(await signalValidator.getAddress());
    });

    it("should allow owner to set profit recipient", async () => {
      const newRecipient = ethers.getAddress("0x7777777777777777777777777777777777777777");
      await expect(arbitrageExecutor.setProfitRecipient(newRecipient))
        .to.emit(arbitrageExecutor, "ProfitRecipientUpdated")
        .withArgs(newRecipient);

      // Reset for other tests
      await arbitrageExecutor.setProfitRecipient(profitRecipientAddr);
    });

    it("should allow owner to approve DEX router", async () => {
      const newRouter = ethers.getAddress("0x8888888888888888888888888888888888888888");
      await expect(arbitrageExecutor.setRouterApproval(newRouter, true))
        .to.emit(arbitrageExecutor, "RouterApprovalUpdated")
        .withArgs(newRouter, true);

      expect(await arbitrageExecutor.approvedRouters(newRouter)).to.equal(true);
    });

    it("should prevent non-owner from updating configuration", async () => {
      const executorAsOther = arbitrageExecutor.connect(other);
      const newValidator = ethers.getAddress("0x9999999999999999999999999999999999999999");

      await expect(
        executorAsOther.setSignalValidator(newValidator)
      ).to.be.revertedWithCustomError(executorAsOther, "OwnableUnauthorizedAccount");
    });
  });

  describe("Flashloan Callback", () => {
    async function createSignal(minProfit: bigint = 0n) {
      const opportunityId = ethers.id(`opportunity-${Date.now()}`);
      const dexAAddr = await dexA.getAddress();
      const dexBAddr = await dexB.getAddress();
      const usdcAddr = await usdc.getAddress();
      const deadline = Math.floor(Date.now() / 1000) + 3600;
      const chainId = await ethers.provider.getNetwork().then(n => n.chainId);

      const signalHash = ethers.keccak256(
        ethers.AbiCoder.defaultAbiCoder().encode(
          ["bytes32", "address", "address", "address", "uint256", "uint256", "uint256", "uint256"],
          [opportunityId, dexAAddr, dexBAddr, usdcAddr, LOAN_AMOUNT, minProfit, deadline, chainId]
        )
      );

      const signature = await teeAccount.signMessage(ethers.getBytes(signalHash));
      const { v, r, s } = ethers.Signature.from(signature);

      return {
        opportunityId,
        dexA: dexAAddr,
        dexB: dexBAddr,
        borrowToken: usdcAddr,
        borrowAmount: LOAN_AMOUNT,
        minProfit,
        deadline,
        signatureV: v,
        signatureR: r,
        signatureS: s,
      };
    }

    it("should execute flashloan callback successfully", async () => {
      const signal = await createSignal(0n);
      const signalData = encodeSignal(signal);

      const executionCountBefore = await arbitrageExecutor.getExecutionCount();

      await lendingPool.flashLoan(
        arbitrageExecutor,
        await usdc.getAddress(),
        LOAN_AMOUNT,
        signalData
      );

      const executionCountAfter = await arbitrageExecutor.getExecutionCount();
      expect(executionCountAfter).to.equal(executionCountBefore + 1n);
    });

    it("should emit ArbitrageExecuted event", async () => {
      const signal = await createSignal(0n);
      const signalData = encodeSignal(signal);

      await expect(
        lendingPool.flashLoan(
          arbitrageExecutor,
          await usdc.getAddress(),
          LOAN_AMOUNT,
          signalData
        )
      )
        .to.emit(arbitrageExecutor, "ArbitrageExecuted");
    });
  });

  describe("Signal Verification", () => {
    async function createSignal(signer: Signer, minProfit: bigint = 0n) {
      const opportunityId = ethers.id(`opportunity-sig-${Date.now()}-${Math.random()}`);
      const dexAAddr = await dexA.getAddress();
      const dexBAddr = await dexB.getAddress();
      const usdcAddr = await usdc.getAddress();
      const deadline = Math.floor(Date.now() / 1000) + 3600;
      const chainId = await ethers.provider.getNetwork().then(n => n.chainId);

      const signalHash = ethers.keccak256(
        ethers.AbiCoder.defaultAbiCoder().encode(
          ["bytes32", "address", "address", "address", "uint256", "uint256", "uint256", "uint256"],
          [opportunityId, dexAAddr, dexBAddr, usdcAddr, LOAN_AMOUNT, minProfit, deadline, chainId]
        )
      );

      const signature = await signer.signMessage(ethers.getBytes(signalHash));
      const { v, r, s } = ethers.Signature.from(signature);

      return {
        opportunityId,
        dexA: dexAAddr,
        dexB: dexBAddr,
        borrowToken: usdcAddr,
        borrowAmount: LOAN_AMOUNT,
        minProfit,
        deadline,
        signatureV: v,
        signatureR: r,
        signatureS: s,
      };
    }

    it("should fail with invalid signature", async () => {
      const signal = await createSignal(other, 0n); // Signed by wrong account
      const signalData = encodeSignal(signal);

      await expect(
        lendingPool.flashLoan(arbitrageExecutor, await usdc.getAddress(), LOAN_AMOUNT, signalData)
      ).to.be.revertedWithCustomError(arbitrageExecutor, "SignalVerificationFailed");
    });

    it("should fail with expired signal", async () => {
      const opportunityId = ethers.id(`opportunity-expired-${Date.now()}`);
      const dexAAddr = await dexA.getAddress();
      const dexBAddr = await dexB.getAddress();
      const usdcAddr = await usdc.getAddress();
      const deadline = Math.floor(Date.now() / 1000) - 3600; // Expired
      const chainId = await ethers.provider.getNetwork().then(n => n.chainId);

      const signalHash = ethers.keccak256(
        ethers.AbiCoder.defaultAbiCoder().encode(
          ["bytes32", "address", "address", "address", "uint256", "uint256", "uint256", "uint256"],
          [opportunityId, dexAAddr, dexBAddr, usdcAddr, LOAN_AMOUNT, 0n, deadline, chainId]
        )
      );

      const signature = await teeAccount.signMessage(ethers.getBytes(signalHash));
      const { v, r, s } = ethers.Signature.from(signature);

      const signal = {
        opportunityId,
        dexA: dexAAddr,
        dexB: dexBAddr,
        borrowToken: usdcAddr,
        borrowAmount: LOAN_AMOUNT,
        minProfit: 0n,
        deadline,
        signatureV: v,
        signatureR: r,
        signatureS: s,
      };

      const signalData = encodeSignal(signal);

      await expect(
        lendingPool.flashLoan(arbitrageExecutor, usdcAddr, LOAN_AMOUNT, signalData)
      ).to.be.revertedWithCustomError(arbitrageExecutor, "SignalExpired");
    });
  });

  describe("Router Approval", () => {
    async function createSignalWithRouter(router: string) {
      const opportunityId = ethers.id(`opportunity-router-${Date.now()}-${Math.random()}`);
      const usdcAddr = await usdc.getAddress();
      const deadline = Math.floor(Date.now() / 1000) + 3600;
      const chainId = await ethers.provider.getNetwork().then(n => n.chainId);

      const signalHash = ethers.keccak256(
        ethers.AbiCoder.defaultAbiCoder().encode(
          ["bytes32", "address", "address", "address", "uint256", "uint256", "uint256", "uint256"],
          [opportunityId, router, router, usdcAddr, LOAN_AMOUNT, 0n, deadline, chainId]
        )
      );

      const signature = await teeAccount.signMessage(ethers.getBytes(signalHash));
      const { v, r, s } = ethers.Signature.from(signature);

      return {
        opportunityId,
        dexA: router,
        dexB: router,
        borrowToken: usdcAddr,
        borrowAmount: LOAN_AMOUNT,
        minProfit: 0n,
        deadline,
        signatureV: v,
        signatureR: r,
        signatureS: s,
      };
    }

    it("should fail with unapproved DEX router", async () => {
      const unapprovedRouter = ethers.getAddress("0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa");
      const signal = await createSignalWithRouter(unapprovedRouter);

      const signalData = encodeSignal(signal);

      await expect(
        lendingPool.flashLoan(arbitrageExecutor, await usdc.getAddress(), LOAN_AMOUNT, signalData)
      ).to.be.revertedWithCustomError(arbitrageExecutor, "UnapprovedRouter");
    });
  });

  describe("Emergency Management", () => {
    it("should allow owner to pause executor", async () => {
      await arbitrageExecutor.pause();
      expect(await arbitrageExecutor.paused()).to.equal(true);

      await arbitrageExecutor.unpause();
    });

    it("should allow owner to unpause executor", async () => {
      await arbitrageExecutor.pause();
      await arbitrageExecutor.unpause();
      expect(await arbitrageExecutor.paused()).to.equal(false);
    });

    it("should allow owner to perform emergency withdrawal", async () => {
      const withdrawAmount = ethers.parseUnits("100", 6);
      const balanceBefore = await usdc.balanceOf(ownerAddr);

      await arbitrageExecutor.emergencyWithdraw(
        await usdc.getAddress(),
        withdrawAmount
      );

      const balanceAfter = await usdc.balanceOf(ownerAddr);
      expect(balanceAfter).to.equal(balanceBefore + withdrawAmount);
    });

    it("should prevent non-owner from pausing", async () => {
      const executorAsOther = arbitrageExecutor.connect(other);

      await expect(executorAsOther.pause()).to.be.revertedWithCustomError(
        executorAsOther,
        "OwnableUnauthorizedAccount"
      );
    });
  });

  describe("Integration Tests", () => {
    it("should complete full arbitrage flow", async () => {
      const signal = await (async () => {
        const opportunityId = ethers.id(`opportunity-full-${Date.now()}`);
        const dexAAddr = await dexA.getAddress();
        const dexBAddr = await dexB.getAddress();
        const usdcAddr = await usdc.getAddress();
        const deadline = Math.floor(Date.now() / 1000) + 3600;
        const chainId = await ethers.provider.getNetwork().then(n => n.chainId);

        const signalHash = ethers.keccak256(
          ethers.AbiCoder.defaultAbiCoder().encode(
            ["bytes32", "address", "address", "address", "uint256", "uint256", "uint256", "uint256"],
            [opportunityId, dexAAddr, dexBAddr, usdcAddr, LOAN_AMOUNT, 0n, deadline, chainId]
          )
        );

        const signature = await teeAccount.signMessage(ethers.getBytes(signalHash));
        const { v, r, s } = ethers.Signature.from(signature);

        return {
          opportunityId,
          dexA: dexAAddr,
          dexB: dexBAddr,
          borrowToken: usdcAddr,
          borrowAmount: LOAN_AMOUNT,
          minProfit: 0n,
          deadline,
          signatureV: v,
          signatureR: r,
          signatureS: s,
        };
      })();

      const signalData = encodeSignal(signal);

      const countBefore = await arbitrageExecutor.getExecutionCount();

      await lendingPool.flashLoan(
        arbitrageExecutor,
        await usdc.getAddress(),
        LOAN_AMOUNT,
        signalData
      );

      const countAfter = await arbitrageExecutor.getExecutionCount();
      expect(countAfter).to.equal(countBefore + 1n);

      // Verify signal was marked as used
      expect(await signalValidator.isSignalUsed(signal.opportunityId)).to.equal(true);
    });
  });
});
