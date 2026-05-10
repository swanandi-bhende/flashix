import { expect } from "chai";
import { ethers } from "hardhat";
import { Contract, Signer } from "ethers";

describe("LendingPool", () => {
  let lendingPool: Contract;
  let usdc: Contract;
  let usdt: Contract;
  let owner: Signer;
  let borrower: Signer;
  let other: Signer;
  let ownerAddr: string;
  let borrowerAddr: string;

  const INITIAL_BALANCE = ethers.parseUnits("1000000", 6); // 1M USDC/USDT
  const FLASHLOAN_AMOUNT = ethers.parseUnits("10000", 6); // 10k
  const FEE_BPS = 9; // 0.09%

  before(async () => {
    [owner, borrower, other] = await ethers.getSigners();
    ownerAddr = await owner.getAddress();
    borrowerAddr = await borrower.getAddress();

    // Deploy mock tokens
    const MockUSDC = await ethers.getContractFactory("MockUSDC");
    usdc = await MockUSDC.deploy();

    const MockUSDT = await ethers.getContractFactory("MockUSDT");
    usdt = await MockUSDT.deploy();

    // Deploy lending pool
    const LendingPool = await ethers.getContractFactory("LendingPool");
    lendingPool = await LendingPool.deploy();

    // Update token listings to use mock tokens
    await lendingPool.setTokenListing(usdc.getAddress(), true);
    await lendingPool.setTokenListing(usdt.getAddress(), true);

    // Fund lending pool with initial balance
    await usdc.transfer(await lendingPool.getAddress(), INITIAL_BALANCE);
    await usdt.transfer(await lendingPool.getAddress(), INITIAL_BALANCE);

    // Fund borrower with tokens for callbacks
    await usdc.transfer(borrowerAddr, INITIAL_BALANCE);
    await usdt.transfer(borrowerAddr, INITIAL_BALANCE);
  });

  describe("Deployment", () => {
    it("should deploy with correct owner", async () => {
      expect(await lendingPool.owner()).to.equal(ownerAddr);
    });

    it("should have FEE_BPS constant set to 9", async () => {
      expect(await lendingPool.FEE_BPS()).to.equal(9);
    });

    it("should initialize with supported tokens", async () => {
      expect(await lendingPool.supportedTokens(usdc.getAddress())).to.equal(true);
      expect(await lendingPool.supportedTokens(usdt.getAddress())).to.equal(true);
    });
  });

  describe("Token Management", () => {
    it("should allow owner to add supported token", async () => {
      const newToken = await ethers.getContractFactory("MockUSDC");
      const newTokenInstance = await newToken.deploy();
      const newTokenAddr = await newTokenInstance.getAddress();

      await lendingPool.setTokenListing(newTokenAddr, true);
      expect(await lendingPool.supportedTokens(newTokenAddr)).to.equal(true);
    });

    it("should allow owner to remove supported token", async () => {
      const newToken = await ethers.getContractFactory("MockUSDC");
      const newTokenInstance = await newToken.deploy();
      const newTokenAddr = await newTokenInstance.getAddress();

      await lendingPool.setTokenListing(newTokenAddr, true);
      await lendingPool.setTokenListing(newTokenAddr, false);
      expect(await lendingPool.supportedTokens(newTokenAddr)).to.equal(false);
    });

    it("should prevent non-owner from modifying token listing", async () => {
      const newToken = await ethers.getContractFactory("MockUSDC");
      const newTokenInstance = await newToken.deploy();
      const newTokenAddr = await newTokenInstance.getAddress();

      const lendingPoolAsOther = lendingPool.connect(other);
      await expect(
        lendingPoolAsOther.setTokenListing(newTokenAddr, true)
      ).to.be.revertedWithCustomError(lendingPoolAsOther, "OwnableUnauthorizedAccount");
    });
  });

  describe("maxFlashLoan", () => {
    it("should return available balance for supported token", async () => {
      const usdcAddr = await usdc.getAddress();
      const maxLoan = await lendingPool.maxFlashLoan(usdcAddr);
      const poolBalance = await usdc.balanceOf(await lendingPool.getAddress());
      expect(maxLoan).to.equal(poolBalance);
    });

    it("should return 0 for unsupported token", async () => {
      const newToken = await ethers.getContractFactory("MockUSDC");
      const newTokenInstance = await newToken.deploy();
      const newTokenAddr = await newTokenInstance.getAddress();

      const maxLoan = await lendingPool.maxFlashLoan(newTokenAddr);
      expect(maxLoan).to.equal(0);
    });

    it("should account for accumulated fees", async () => {
      const usdcAddr = await usdc.getAddress();
      const initialMax = await lendingPool.maxFlashLoan(usdcAddr);

      // Simulate fee accumulation
      const feeAmount = ethers.parseUnits("100", 6);
      await usdc.transfer(await lendingPool.getAddress(), feeAmount);

      const newMax = await lendingPool.maxFlashLoan(usdcAddr);
      expect(newMax).to.equal(initialMax + feeAmount);
    });
  });

  describe("flashFee", () => {
    it("should calculate correct fee for 0.09%", async () => {
      const amount = ethers.parseUnits("10000", 6); // 10k
      const expectedFee = (amount * BigInt(FEE_BPS)) / BigInt(10000);
      const actualFee = await lendingPool.flashFee(usdc.getAddress(), amount);
      expect(actualFee).to.equal(expectedFee);
    });

    it("should handle fee calculation at boundary (1 USDT)", async () => {
      const amount = ethers.parseUnits("1", 6);
      const fee = await lendingPool.flashFee(usdc.getAddress(), amount);
      expect(fee).to.equal(900); // 1e6 * 9 / 10000
    });

    it("should handle fee calculation at boundary (1M USDT)", async () => {
      const amount = ethers.parseUnits("1000000", 6); // 1M
      const fee = await lendingPool.flashFee(usdc.getAddress(), amount);
      const expected = (amount * BigInt(FEE_BPS)) / BigInt(10000);
      expect(fee).to.equal(expected);
    });
  });

  describe("flashLoan - Basic Functionality", () => {
    it("should execute flashloan with correct repayment", async () => {
      // Deploy simple borrower contract
      const SimpleBorrower = await ethers.getContractFactory("SimpleBorrower");
      const borrowerContract = await SimpleBorrower.deploy();
      const borrowerContractAddr = await borrowerContract.getAddress();

      // Give borrower contract tokens to repay
      await usdc.transfer(borrowerContractAddr, ethers.parseUnits("1000", 6));

      const loanAmount = ethers.parseUnits("5000", 6);
      const usdcAddr = await usdc.getAddress();

      // Execute flashloan
      await lendingPool.flashLoan(borrowerContract, usdcAddr, loanAmount, "0x");

      // Verify accumulated fees increased
      const fees = await lendingPool.getAccumulatedFees(usdcAddr);
      expect(fees).to.be.greaterThan(0);
    });

    it("should fail when loan amount exceeds available liquidity", async () => {
      const SimpleBorrower = await ethers.getContractFactory("SimpleBorrower");
      const borrowerContract = await SimpleBorrower.deploy();

      const usdcAddr = await usdc.getAddress();
      const maxLoan = await lendingPool.maxFlashLoan(usdcAddr);
      const excessAmount = maxLoan + ethers.parseUnits("1", 6);

      await expect(
        lendingPool.flashLoan(borrowerContract, usdcAddr, excessAmount, "0x")
      ).to.be.revertedWithCustomError(lendingPool, "InsufficientLiquidity");
    });

    it("should fail when token is not supported", async () => {
      const SimpleBorrower = await ethers.getContractFactory("SimpleBorrower");
      const borrowerContract = await SimpleBorrower.deploy();

      const newToken = await ethers.getContractFactory("MockUSDC");
      const newTokenInstance = await newToken.deploy();
      const newTokenAddr = await newTokenInstance.getAddress();

      await expect(
        lendingPool.flashLoan(
          borrowerContract,
          newTokenAddr,
          ethers.parseUnits("1000", 6),
          "0x"
        )
      ).to.be.revertedWithCustomError(lendingPool, "UnsupportedToken");
    });
  });

  describe("flashLoan - Repayment Validation", () => {
    it("should fail when repayment is short by 1 wei", async () => {
      const ShortRepaymentBorrower = await ethers.getContractFactory(
        "ShortRepaymentBorrower"
      );
      const borrowerContract = await ShortRepaymentBorrower.deploy(
        await lendingPool.getAddress(),
        await usdc.getAddress()
      );

      const loanAmount = ethers.parseUnits("1000", 6);
      const usdcAddr = await usdc.getAddress();

      // Give borrower contract the loan amount
      await usdc.transfer(await borrowerContract.getAddress(), loanAmount);

      await expect(
        lendingPool.flashLoan(borrowerContract, usdcAddr, loanAmount, "0x")
      ).to.be.revertedWithCustomError(lendingPool, "InsufficientRepayment");
    });

    it("should fail when callback returns wrong hash", async () => {
      const WrongHashBorrower = await ethers.getContractFactory(
        "WrongHashBorrower"
      );
      const borrowerContract = await WrongHashBorrower.deploy(
        await usdc.getAddress()
      );

      const loanAmount = ethers.parseUnits("1000", 6);
      await usdc.transfer(await borrowerContract.getAddress(), loanAmount);

      const usdcAddr = await usdc.getAddress();

      await expect(
        lendingPool.flashLoan(borrowerContract, usdcAddr, loanAmount, "0x")
      ).to.be.revertedWithCustomError(lendingPool, "InvalidFlashLoanReturn");
    });
  });

  describe("Emergency Pause", () => {
    it("should prevent flashloans when paused", async () => {
      const SimpleBorrower = await ethers.getContractFactory("SimpleBorrower");
      const borrowerContract = await SimpleBorrower.deploy();
      const borrowerContractAddr = await borrowerContract.getAddress();

      await usdc.transfer(borrowerContractAddr, ethers.parseUnits("1000", 6));

      // Pause the pool
      await lendingPool.emergencyPause();

      const loanAmount = ethers.parseUnits("100", 6);
      const usdcAddr = await usdc.getAddress();

      // Attempt to flashloan should fail
      await expect(
        lendingPool.flashLoan(borrowerContract, usdcAddr, loanAmount, "0x")
      ).to.be.revertedWithCustomError(lendingPool, "EnforcedPause");

      // Unpause for other tests
      await lendingPool.emergencyUnpause();
    });
  });

  describe("Reentrancy Protection", () => {
    it("should prevent reentrancy attacks", async () => {
      const ReentrantBorrower = await ethers.getContractFactory(
        "ReentrantBorrower"
      );
      const borrowerContract = await ReentrantBorrower.deploy(
        await lendingPool.getAddress()
      );
      const borrowerContractAddr = await borrowerContract.getAddress();

      const usdcAddr = await usdc.getAddress();
      await usdc.transfer(borrowerContractAddr, ethers.parseUnits("100000", 6));

      const loanAmount = ethers.parseUnits("1000", 6);

      // Reentrancy attack should fail
      await expect(
        lendingPool.flashLoan(borrowerContract, usdcAddr, loanAmount, "0x")
      ).to.be.revertedWithCustomError(lendingPool, "ReentrancyGuardReentrantCall");
    });
  });

  describe("Fee Withdrawal", () => {
    it("should allow owner to withdraw accumulated fees", async () => {
      const SimpleBorrower = await ethers.getContractFactory("SimpleBorrower");
      const borrowerContract = await SimpleBorrower.deploy();
      const borrowerContractAddr = await borrowerContract.getAddress();

      await usdc.transfer(borrowerContractAddr, ethers.parseUnits("10000", 6));

      const usdcAddr = await usdc.getAddress();
      const loanAmount = ethers.parseUnits("5000", 6);

      // Execute flashloan to accumulate fees
      await lendingPool.flashLoan(borrowerContract, usdcAddr, loanAmount, "0x");

      // Get accumulated fees
      const fees = await lendingPool.getAccumulatedFees(usdcAddr);
      expect(fees).to.be.greaterThan(0);

      // Withdraw fees
      const ownerBalanceBefore = await usdc.balanceOf(ownerAddr);
      await lendingPool.withdrawFees(usdcAddr);
      const ownerBalanceAfter = await usdc.balanceOf(ownerAddr);

      expect(ownerBalanceAfter).to.equal(ownerBalanceBefore + fees);
      expect(await lendingPool.getAccumulatedFees(usdcAddr)).to.equal(0);
    });

    it("should prevent non-owner from withdrawing fees", async () => {
      const lendingPoolAsOther = lendingPool.connect(other);
      const usdcAddr = await usdc.getAddress();

      await expect(
        lendingPoolAsOther.withdrawFees(usdcAddr)
      ).to.be.revertedWithCustomError(lendingPoolAsOther, "OwnableUnauthorizedAccount");
    });

    it("should fail when trying to withdraw zero fees", async () => {
      const newToken = await ethers.getContractFactory("MockUSDC");
      const newTokenInstance = await newToken.deploy();
      const newTokenAddr = await newTokenInstance.getAddress();

      await lendingPool.setTokenListing(newTokenAddr, true);

      await expect(
        lendingPool.withdrawFees(newTokenAddr)
      ).to.be.revertedWith("No fees to withdraw");
    });
  });

  describe("Events", () => {
    it("should emit FlashLoanExecuted event", async () => {
      const SimpleBorrower = await ethers.getContractFactory("SimpleBorrower");
      const borrowerContract = await SimpleBorrower.deploy();
      const borrowerContractAddr = await borrowerContract.getAddress();

      await usdc.transfer(borrowerContractAddr, ethers.parseUnits("1000", 6));

      const usdcAddr = await usdc.getAddress();
      const loanAmount = ethers.parseUnits("1000", 6);
      const expectedFee = (loanAmount * BigInt(FEE_BPS)) / BigInt(10000);

      await expect(lendingPool.flashLoan(borrowerContract, usdcAddr, loanAmount, "0x"))
        .to.emit(lendingPool, "FlashLoanExecuted")
        .withArgs(borrowerContractAddr, usdcAddr, loanAmount, expectedFee);
    });

    it("should emit TokenListingUpdated event", async () => {
      const newToken = await ethers.getContractFactory("MockUSDC");
      const newTokenInstance = await newToken.deploy();
      const newTokenAddr = await newTokenInstance.getAddress();

      await expect(lendingPool.setTokenListing(newTokenAddr, true))
        .to.emit(lendingPool, "TokenListingUpdated")
        .withArgs(newTokenAddr, true);
    });
  });
});
