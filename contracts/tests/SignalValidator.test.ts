import { expect } from "chai";
import { ethers } from "hardhat";
import { Contract, Signer } from "ethers";

describe("SignalValidator", () => {
  let signalValidator: Contract;
  let owner: Signer;
  let teeAccount: Signer;
  let otherAccount: Signer;
  let ownerAddr: string;
  let teeAddr: string;
  let otherAddr: string;

  before(async () => {
    [owner, teeAccount, otherAccount] = await ethers.getSigners();
    ownerAddr = await owner.getAddress();
    teeAddr = await teeAccount.getAddress();
    otherAddr = await otherAccount.getAddress();

    // Deploy signal validator with TEE address as trusted signer
    const SignalValidator = await ethers.getContractFactory("SignalValidator");
    signalValidator = await SignalValidator.deploy(teeAddr);
  });

  async function createAndSignSignal(signer: Signer) {
    const opportunityId = ethers.id(`opportunity-${Date.now()}-${Math.random()}`);
    const dexA = ethers.getAddress("0x1111111111111111111111111111111111111111");
    const dexB = ethers.getAddress("0x2222222222222222222222222222222222222222");
    const borrowToken = ethers.getAddress("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"); // USDC
    const borrowAmount = ethers.parseUnits("10000", 6);
    const minProfit = ethers.parseUnits("100", 6);
    const deadline = Math.floor(Date.now() / 1000) + 3600; // 1 hour from now
    const chainId = await ethers.provider.getNetwork().then(n => n.chainId);

    const hash = ethers.keccak256(
      ethers.AbiCoder.defaultAbiCoder().encode(
        ["bytes32", "address", "address", "address", "uint256", "uint256", "uint256", "uint256"],
        [opportunityId, dexA, dexB, borrowToken, borrowAmount, minProfit, deadline, chainId]
      )
    );

    const messageHash = ethers.hashMessage(ethers.getBytes(hash));

    const signature = await signer.signMessage(ethers.getBytes(hash));
    const { v, r, s } = ethers.Signature.from(signature);

    return {
      signal: {
        opportunityId,
        dexA,
        dexB,
        borrowToken,
        borrowAmount,
        minProfit,
        deadline,
        signatureV: v,
        signatureR: r,
        signatureS: s,
      },
      hash,
      messageHash,
    };
  }

  describe("Deployment", () => {
    it("should deploy with correct owner", async () => {
      expect(await signalValidator.owner()).to.equal(ownerAddr);
    });

    it("should set trusted signer on deployment", async () => {
      expect(await signalValidator.getTrustedSigner()).to.equal(teeAddr);
    });

    it("should prevent zero address as trusted signer", async () => {
      const SignalValidator = await ethers.getContractFactory("SignalValidator");
      await expect(SignalValidator.deploy(ethers.ZeroAddress)).to.be.revertedWith(
        "Invalid signer address"
      );
    });
  });

  describe("Signal Verification", () => {

    it("should verify signal signed by trusted signer", async () => {
      const { signal } = await createAndSignSignal(teeAccount);

      const isValid = await signalValidator.verify.staticCall(signal);
      expect(isValid).to.equal(true);

      await signalValidator.verify(signal);
    });

    it("should reject signal signed by untrusted signer", async () => {
      const { signal } = await createAndSignSignal(otherAccount);

      await expect(signalValidator.verify(signal)).to.be.revertedWithCustomError(
        signalValidator,
        "InvalidSignature"
      );
    });

    it("should reject expired signal", async () => {
      const opportunityId = ethers.id("opportunity-expired");
      const dexA = ethers.getAddress("0x1111111111111111111111111111111111111111");
      const dexB = ethers.getAddress("0x2222222222222222222222222222222222222222");
      const borrowToken = ethers.getAddress("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48");
      const borrowAmount = ethers.parseUnits("10000", 6);
      const minProfit = ethers.parseUnits("100", 6);
      const deadline = Math.floor(Date.now() / 1000) - 3600; // 1 hour ago (expired)
      const chainId = await ethers.provider.getNetwork().then(n => n.chainId);

      const hash = ethers.keccak256(
        ethers.AbiCoder.defaultAbiCoder().encode(
          ["bytes32", "address", "address", "address", "uint256", "uint256", "uint256", "uint256"],
          [opportunityId, dexA, dexB, borrowToken, borrowAmount, minProfit, deadline, chainId]
        )
      );
      const signature = await teeAccount.signMessage(ethers.getBytes(hash));
      const { v, r, s } = ethers.Signature.from(signature);

      const signal = {
        opportunityId,
        dexA,
        dexB,
        borrowToken,
        borrowAmount,
        minProfit,
        deadline,
        signatureV: v,
        signatureR: r,
        signatureS: s,
      };

      await expect(signalValidator.verify(signal)).to.be.revertedWithCustomError(
        signalValidator,
        "SignalExpired"
      );
    });

    it("should prevent replay of same signal", async () => {
      const { signal } = await createAndSignSignal(teeAccount);

      // First execution should succeed
      const tx1 = await signalValidator.verify.staticCall(signal);
      expect(tx1).to.equal(true);
      await signalValidator.verify(signal);

      // Second execution with same signal should fail
      await expect(signalValidator.verify(signal)).to.be.revertedWithCustomError(
        signalValidator,
        "SignalAlreadyUsed"
      );
    });

    it("should reject signal with zero opportunity ID", async () => {
      const dexA = ethers.getAddress("0x1111111111111111111111111111111111111111");
      const dexB = ethers.getAddress("0x2222222222222222222222222222222222222222");
      const borrowToken = ethers.getAddress("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48");
      const borrowAmount = ethers.parseUnits("10000", 6);
      const minProfit = ethers.parseUnits("100", 6);
      const deadline = Math.floor(Date.now() / 1000) + 3600;
      const chainId = await ethers.provider.getNetwork().then(n => n.chainId);

      const hash = ethers.keccak256(
        ethers.AbiCoder.defaultAbiCoder().encode(
          ["bytes32", "address", "address", "address", "uint256", "uint256", "uint256", "uint256"],
          [ethers.ZeroHash, dexA, dexB, borrowToken, borrowAmount, minProfit, deadline, chainId]
        )
      );
      const signature = await teeAccount.signMessage(ethers.getBytes(hash));
      const { v, r, s } = ethers.Signature.from(signature);

      const signal = {
        opportunityId: ethers.ZeroHash,
        dexA,
        dexB,
        borrowToken,
        borrowAmount,
        minProfit,
        deadline,
        signatureV: v,
        signatureR: r,
        signatureS: s,
      };

      await expect(signalValidator.verify(signal)).to.be.revertedWithCustomError(
        signalValidator,
        "InvalidOpportunityId"
      );
    });
  });

  describe("Batch Verification", () => {
    it("should verify multiple signals in batch", async () => {
      const signals = [];

      for (let i = 0; i < 3; i++) {
        const opportunityId = ethers.id(`opportunity-batch-${i}`);
        const dexA = ethers.getAddress("0x1111111111111111111111111111111111111111");
        const dexB = ethers.getAddress("0x2222222222222222222222222222222222222222");
        const borrowToken = ethers.getAddress("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48");
        const borrowAmount = ethers.parseUnits("10000", 6);
        const minProfit = ethers.parseUnits("100", 6);
        const deadline = Math.floor(Date.now() / 1000) + 3600;
        const chainId = await ethers.provider.getNetwork().then(n => n.chainId);

        const hash = ethers.keccak256(
          ethers.AbiCoder.defaultAbiCoder().encode(
            ["bytes32", "address", "address", "address", "uint256", "uint256", "uint256", "uint256"],
            [opportunityId, dexA, dexB, borrowToken, borrowAmount, minProfit, deadline, chainId]
          )
        );
        const signature = await teeAccount.signMessage(ethers.getBytes(hash));
        const { v, r, s } = ethers.Signature.from(signature);

        signals.push({
          opportunityId,
          dexA,
          dexB,
          borrowToken,
          borrowAmount,
          minProfit,
          deadline,
          signatureV: v,
          signatureR: r,
          signatureS: s,
        });
      }

      const success = await signalValidator.verifyBatch.staticCall(signals);
      expect(success).to.equal(true);

      await signalValidator.verifyBatch(signals);

      // All signals should be marked as used
      for (const signal of signals) {
        expect(await signalValidator.isSignalUsed(signal.opportunityId)).to.equal(true);
      }
    });
  });

  describe("Trusted Signer Management", () => {
    it("should allow owner to update trusted signer", async () => {
      const newSigner = ethers.getAddress("0x3333333333333333333333333333333333333333");

      await expect(signalValidator.setTrustedSigner(newSigner))
        .to.emit(signalValidator, "TrustedSignerUpdated")
        .withArgs(teeAddr, newSigner);

      expect(await signalValidator.getTrustedSigner()).to.equal(newSigner);

      // Reset for other tests
      await signalValidator.setTrustedSigner(teeAddr);
    });

    it("should prevent non-owner from updating trusted signer", async () => {
      const validatorAsOther = signalValidator.connect(otherAccount);
      const newSigner = ethers.getAddress("0x4444444444444444444444444444444444444444");

      await expect(validatorAsOther.setTrustedSigner(newSigner)).to.be.revertedWithCustomError(
        validatorAsOther,
        "OwnableUnauthorizedAccount"
      );
    });

    it("should prevent zero address as trusted signer", async () => {
      await expect(
        signalValidator.setTrustedSigner(ethers.ZeroAddress)
      ).to.be.revertedWith("Invalid signer address");
    });
  });

  describe("Signal Status Queries", () => {
    it("should correctly report used signals", async () => {
      const { signal } = await createAndSignSignal(teeAccount);

      expect(await signalValidator.isSignalUsed(signal.opportunityId)).to.equal(false);

      await signalValidator.verify(signal);

      expect(await signalValidator.isSignalUsed(signal.opportunityId)).to.equal(true);
    });

    it("should correctly report valid signals", async () => {
      const { signal } = await createAndSignSignal(teeAccount);

      expect(await signalValidator.isSignalValid(signal)).to.equal(true);
    });

    it("should report invalid signals (expired)", async () => {
      const opportunityId = ethers.id("opportunity-invalid-expired");
      const dexA = ethers.getAddress("0x1111111111111111111111111111111111111111");
      const dexB = ethers.getAddress("0x2222222222222222222222222222222222222222");
      const borrowToken = ethers.getAddress("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48");
      const borrowAmount = ethers.parseUnits("10000", 6);
      const minProfit = ethers.parseUnits("100", 6);
      const deadline = Math.floor(Date.now() / 1000) - 3600; // Expired
      const chainId = await ethers.provider.getNetwork().then(n => n.chainId);

      const hash = ethers.keccak256(
        ethers.AbiCoder.defaultAbiCoder().encode(
          ["bytes32", "address", "address", "address", "uint256", "uint256", "uint256", "uint256"],
          [opportunityId, dexA, dexB, borrowToken, borrowAmount, minProfit, deadline, chainId]
        )
      );
      const signature = await teeAccount.signMessage(ethers.getBytes(hash));
      const { v, r, s } = ethers.Signature.from(signature);

      const signal = {
        opportunityId,
        dexA,
        dexB,
        borrowToken,
        borrowAmount,
        minProfit,
        deadline,
        signatureV: v,
        signatureR: r,
        signatureS: s,
      };

      expect(await signalValidator.isSignalValid(signal)).to.equal(false);
    });

    it("should report invalid signals (already used)", async () => {
      const { signal } = await createAndSignSignal(teeAccount);

      await signalValidator.verify(signal);

      expect(await signalValidator.isSignalValid(signal)).to.equal(false);
    });
  });

  describe("Signal Reset", () => {
    it("should allow owner to reset used signals", async () => {
      const { signal } = await createAndSignSignal(teeAccount);

      await signalValidator.verify(signal);
      expect(await signalValidator.isSignalUsed(signal.opportunityId)).to.equal(true);

      await signalValidator.resetSignal(signal.opportunityId);
      expect(await signalValidator.isSignalUsed(signal.opportunityId)).to.equal(false);
    });

    it("should prevent non-owner from resetting signals", async () => {
      const { signal } = await createAndSignSignal(teeAccount);

      await signalValidator.verify(signal);

      const validatorAsOther = signalValidator.connect(otherAccount);

      await expect(
        validatorAsOther.resetSignal(signal.opportunityId)
      ).to.be.revertedWithCustomError(validatorAsOther, "OwnableUnauthorizedAccount");
    });
  });
});
