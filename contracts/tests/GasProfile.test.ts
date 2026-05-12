import { expect } from "chai";
import { ethers } from "hardhat";
import { loadFixture } from "@nomicfoundation/hardhat-network-helpers";

import { buildSignals, deployGasFixture, LOAN_AMOUNT, toSingleTradeSignal } from "./gasHelpers";

describe("GasProfile", () => {
  it("single trade gas usage within budget", async () => {
    const { executorV2, teeAccount, dexA, dexB, usdc } = await loadFixture(deployGasFixture);
    const { signalsV2 } = await buildSignals(teeAccount, dexA, dexB, usdc, 1);
    const singleSignal = toSingleTradeSignal(signalsV2[0], await usdc.getAddress());

    const tx = await executorV2.executeArbitrage(singleSignal);
    const receipt = await tx.wait();

    expect(receipt?.gasUsed ?? 0n).to.be.lte(180_000n);
  });

  it("batch of 2 trades per-trade gas within budget", async () => {
    const { executorV2, teeAccount, dexA, dexB, usdc } = await loadFixture(deployGasFixture);
    const { signalsV2 } = await buildSignals(teeAccount, dexA, dexB, usdc, 2);

    const params = {
      signals: signalsV2,
      borrowToken: await usdc.getAddress(),
      totalBorrowAmount: LOAN_AMOUNT * 2n,
      batchDeadline: signalsV2[1].deadline,
      activateMevBurn: false,
      mevBurnAmount: 0n,
    };

    const tx = await executorV2.executeArbitrageBatch(params);
    const receipt = await tx.wait();

    expect((receipt?.gasUsed ?? 0n) / 2n).to.be.lte(150_000n);
  });

  it("batch of 5 trades per-trade gas within budget", async () => {
    const { executorV2, teeAccount, dexA, dexB, usdc } = await loadFixture(deployGasFixture);
    const { signalsV2 } = await buildSignals(teeAccount, dexA, dexB, usdc, 5);

    const params = {
      signals: signalsV2,
      borrowToken: await usdc.getAddress(),
      totalBorrowAmount: LOAN_AMOUNT * 5n,
      batchDeadline: signalsV2[4].deadline,
      activateMevBurn: false,
      mevBurnAmount: 0n,
    };

    const tx = await executorV2.executeArbitrageBatch(params);
    const receipt = await tx.wait();

    expect((receipt?.gasUsed ?? 0n) / 5n).to.be.lte(150_000n);
  });

  it("MEV burn adds less than 5000 gas overhead", async () => {
    const { executorV2, teeAccount, dexA, dexB, usdc } = await loadFixture(deployGasFixture);
    const { signalsV2 } = await buildSignals(teeAccount, dexA, dexB, usdc, 2);
    const singleSignal = toSingleTradeSignal(signalsV2[0], await usdc.getAddress());
    const burnSignal = toSingleTradeSignal(signalsV2[1], await usdc.getAddress());

    await executorV2.setMevBurnEnabled(true);
    await executorV2.depositMevFund({ value: ethers.parseEther("1") });

    const baseTx = await executorV2.executeArbitrage(singleSignal);
    const baseReceipt = await baseTx.wait();

    const burnAmount = await executorV2.estimateMevBurnAmount(ethers.parseUnits("100", 6));
    const burnTx = await executorV2.executeArbitrageBatch({
      signals: [signalsV2[1]],
      borrowToken: await usdc.getAddress(),
      totalBorrowAmount: LOAN_AMOUNT,
      batchDeadline: burnSignal.deadline,
      activateMevBurn: true,
      mevBurnAmount: burnAmount,
    });
    const burnReceipt = await burnTx.wait();

    expect((burnReceipt?.gasUsed ?? 0n) - (baseReceipt?.gasUsed ?? 0n)).to.be.lte(5_000n);
  });
});
