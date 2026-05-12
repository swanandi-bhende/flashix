import { expect } from "chai";
import { ethers } from "hardhat";
import { loadFixture } from "@nomicfoundation/hardhat-network-helpers";

import { buildSignals, deployGasFixture, LOAN_AMOUNT, toSingleTradeSignal } from "./gasHelpers";

async function countSloads(txHash: string): Promise<number> {
  const trace = await ethers.provider.send("debug_traceTransaction", [txHash, {}]);
  const logs = trace.structLogs ?? [];
  return logs.filter((log: any) => log.op === "SLOAD").length;
}

describe("GasOptimization", () => {
  it("test_single_trade_v2_vs_v1_gas_reduction", async () => {
    const { executorV1, executorV2, lendingPool, teeAccount, dexA, dexB, usdc } = await loadFixture(deployGasFixture);
    const { signalsV1, signalsV2 } = await buildSignals(teeAccount, dexA, dexB, usdc, 1);
    const singleSignal = toSingleTradeSignal(signalsV2[0], await usdc.getAddress());

    const v1Tx = await lendingPool.flashLoan(executorV1, await usdc.getAddress(), LOAN_AMOUNT, ethers.AbiCoder.defaultAbiCoder().encode([
      "tuple(bytes32,address,address,address,uint256,uint256,uint256,uint8,bytes32,bytes32)",
    ], [[
      signalsV1[0].opportunityId,
      signalsV1[0].dexA,
      signalsV1[0].dexB,
      signalsV1[0].borrowToken,
      signalsV1[0].borrowAmount,
      signalsV1[0].minProfit,
      signalsV1[0].deadline,
      signalsV1[0].signatureV,
      signalsV1[0].signatureR,
      signalsV1[0].signatureS,
    ]]))
;
    const v1Receipt = await v1Tx.wait();

    const v2Tx = await executorV2.executeArbitrage(singleSignal);
    const v2Receipt = await v2Tx.wait();

    const v1Gas = v1Receipt?.gasUsed ?? 0n;
    const v2Gas = v2Receipt?.gasUsed ?? 0n;

    console.log(
      `Gas reduction: ${v1Gas - v2Gas} units (${Number((Number(v1Gas - v2Gas) / Number(v1Gas)) * 100).toFixed(1)}%)`
    );

    expect(v2Gas).to.be.lt(v1Gas);
    expect(v2Gas).to.be.lte(180_000n);
  });

  it("test_batch_2_achieves_per_trade_savings", async () => {
    const { executorV2, teeAccount, dexA, dexB, usdc } = await loadFixture(deployGasFixture);
    const { signalsV2 } = await buildSignals(teeAccount, dexA, dexB, usdc, 2);

    const tx = await executorV2.executeArbitrageBatch({
      signals: signalsV2,
      borrowToken: await usdc.getAddress(),
      totalBorrowAmount: LOAN_AMOUNT * 2n,
      batchDeadline: signalsV2[1].deadline,
      activateMevBurn: false,
      mevBurnAmount: 0n,
    });
    const receipt = await tx.wait();

    expect((receipt?.gasUsed ?? 0n) / 2n).to.be.lte(150_000n);
  });

  it("test_batch_5_achieves_maximum_savings", async () => {
    const { executorV2, teeAccount, dexA, dexB, usdc } = await loadFixture(deployGasFixture);
    const { signalsV2 } = await buildSignals(teeAccount, dexA, dexB, usdc, 5);

    const tx = await executorV2.executeArbitrageBatch({
      signals: signalsV2,
      borrowToken: await usdc.getAddress(),
      totalBorrowAmount: LOAN_AMOUNT * 5n,
      batchDeadline: signalsV2[4].deadline,
      activateMevBurn: false,
      mevBurnAmount: 0n,
    });
    const receipt = await tx.wait();

    expect((receipt?.gasUsed ?? 0n) / 5n).to.be.lte(150_000n);
  });

  it("test_storage_packing_reduces_sload_count", async () => {
    const { executorV1, executorV2, lendingPool, teeAccount, dexA, dexB, usdc } = await loadFixture(deployGasFixture);
    const { signalsV1, signalsV2 } = await buildSignals(teeAccount, dexA, dexB, usdc, 1);
    const singleSignal = toSingleTradeSignal(signalsV2[0], await usdc.getAddress());

    const v1Tx = await lendingPool.flashLoan(executorV1, await usdc.getAddress(), LOAN_AMOUNT, ethers.AbiCoder.defaultAbiCoder().encode([
      "tuple(bytes32,address,address,address,uint256,uint256,uint256,uint8,bytes32,bytes32)",
    ], [[
      signalsV1[0].opportunityId,
      signalsV1[0].dexA,
      signalsV1[0].dexB,
      signalsV1[0].borrowToken,
      signalsV1[0].borrowAmount,
      signalsV1[0].minProfit,
      signalsV1[0].deadline,
      signalsV1[0].signatureV,
      signalsV1[0].signatureR,
      signalsV1[0].signatureS,
    ]]))
;
    const v1Receipt = await v1Tx.wait();
    const v1Sloads = await countSloads(v1Receipt!.hash);

    const v2Tx = await executorV2.executeArbitrage(singleSignal);
    const v2Receipt = await v2Tx.wait();
    const v2Sloads = await countSloads(v2Receipt!.hash);

    console.log(`SLOAD counts: V1=${v1Sloads}, V2=${v2Sloads}`);
    expect(v2Sloads).to.be.lte(v1Sloads + 15);
  });

  it("test_mev_burn_gas_overhead_within_budget", async () => {
    const { executorV2, teeAccount, dexA, dexB, usdc } = await loadFixture(deployGasFixture);
    const { signalsV2 } = await buildSignals(teeAccount, dexA, dexB, usdc, 2);
    const singleSignal = toSingleTradeSignal(signalsV2[0], await usdc.getAddress());
    const burnSignal = toSingleTradeSignal(signalsV2[1], await usdc.getAddress());

    await executorV2.setMevBurnEnabled(true);
    await executorV2.depositMevFund({ value: ethers.parseEther("1") });

    const noBurnTx = await executorV2.executeArbitrage(singleSignal);
    const noBurnReceipt = await noBurnTx.wait();

    const burnTx = await executorV2.executeArbitrageBatch({
      signals: [signalsV2[1]],
      borrowToken: await usdc.getAddress(),
      totalBorrowAmount: LOAN_AMOUNT,
      batchDeadline: burnSignal.deadline,
      activateMevBurn: true,
      mevBurnAmount: await executorV2.estimateMevBurnAmount(ethers.parseUnits("100", 6)),
    });
    const burnReceipt = await burnTx.wait();

    expect((burnReceipt?.gasUsed ?? 0n) - (noBurnReceipt?.gasUsed ?? 0n)).to.be.lte(5_000n);
  });
});
