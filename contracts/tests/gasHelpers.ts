import { ethers } from "hardhat";
import { Contract, Signer } from "ethers";

export const INITIAL_BALANCE = ethers.parseUnits("1000000", 6);
export const LOAN_AMOUNT = ethers.parseUnits("10000", 6);

export interface GasFixture {
  owner: Signer;
  teeAccount: Signer;
  profitRecipient: Signer;
  usdc: Contract;
  dexA: Contract;
  dexB: Contract;
  lendingPool: Contract;
  signalValidator: Contract;
  executorV1: Contract;
  executorV2: Contract;
}

export async function deployGasFixture(): Promise<GasFixture> {
  const [owner, teeAccount, profitRecipient] = await ethers.getSigners();

  const MockUSDC = await ethers.getContractFactory("MockUSDC");
  const usdc = await MockUSDC.deploy();

  const MockDEXRouter = await ethers.getContractFactory("MockDEXRouter");
  const dexA = await MockDEXRouter.deploy();
  const dexB = await MockDEXRouter.deploy();

  const LendingPool = await ethers.getContractFactory("LendingPool");
  const lendingPool = await LendingPool.deploy();
  const usdcAddr = await usdc.getAddress();

  await lendingPool.setTokenListing(usdcAddr, true);
  await usdc.transfer(await lendingPool.getAddress(), INITIAL_BALANCE);

  const SignalValidator = await ethers.getContractFactory("SignalValidator");
  const signalValidator = await SignalValidator.deploy(await teeAccount.getAddress());

  const ArbitrageExecutor = await ethers.getContractFactory("ArbitrageExecutor");
  const executorV1 = await ArbitrageExecutor.deploy(await profitRecipient.getAddress());
  await executorV1.setLendingPool(await lendingPool.getAddress());
  await executorV1.setSignalValidator(await signalValidator.getAddress());
  await executorV1.setRouterApproval(await dexA.getAddress(), true);
  await executorV1.setRouterApproval(await dexB.getAddress(), true);

  const ArbitrageExecutorV2 = await ethers.getContractFactory("ArbitrageExecutorV2");
  const executorV2 = await ArbitrageExecutorV2.deploy(await profitRecipient.getAddress());
  await executorV2.setLendingPool(await lendingPool.getAddress());
  await executorV2.setSignalValidator(await signalValidator.getAddress());
  await executorV2.setDefaultBorrowToken(usdcAddr);
  await executorV2.setRouterApproval(await dexA.getAddress(), true);
  await executorV2.setRouterApproval(await dexB.getAddress(), true);

  await usdc.transfer(await executorV1.getAddress(), INITIAL_BALANCE);
  await usdc.transfer(await executorV2.getAddress(), INITIAL_BALANCE);

  await dexA.setExchangeRate(usdcAddr, usdcAddr, ethers.parseUnits("1", 18));
  await dexB.setExchangeRate(usdcAddr, usdcAddr, ethers.parseUnits("1", 18));

  return {
    owner,
    teeAccount,
    profitRecipient,
    usdc,
    dexA,
    dexB,
    lendingPool,
    signalValidator,
    executorV1,
    executorV2,
  };
}

export async function buildSignals(teeAccount: Signer, dexA: Contract, dexB: Contract, usdc: Contract, count = 1) {
  const chainId = await ethers.provider.getNetwork().then((network) => network.chainId);
  const signalsV1: any[] = [];
  const signalsV2: any[] = [];

  for (let index = 0; index < count; index++) {
    const opportunityId = ethers.id(`opportunity-${count}-${index}-${Date.now()}`);
    const deadline = Math.floor(Date.now() / 1000) + 3600;
    const dexAAddr = await dexA.getAddress();
    const dexBAddr = await dexB.getAddress();
    const usdcAddr = await usdc.getAddress();

    const signalHash = ethers.keccak256(
      ethers.AbiCoder.defaultAbiCoder().encode(
        ["bytes32", "address", "address", "address", "uint256", "uint256", "uint256", "uint256"],
        [opportunityId, dexAAddr, dexBAddr, usdcAddr, LOAN_AMOUNT, 0n, deadline, chainId]
      )
    );

    const signature = await teeAccount.signMessage(ethers.getBytes(signalHash));
    const { v, r, s } = ethers.Signature.from(signature);

    signalsV1.push({
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
    });

    signalsV2.push({
      opportunityId,
      primaryDex: dexAAddr,
      counterDex: dexBAddr,
      borrowAmount: LOAN_AMOUNT,
      collateralRequired: 0n,
      minProfit: 0n,
      deadline,
      v,
      r,
      s,
    });
  }

  return { signalsV1, signalsV2 };
}

export function toSingleTradeSignal(signal: any, borrowToken: string) {
  return {
    opportunityId: signal.opportunityId,
    dexA: signal.primaryDex,
    dexB: signal.counterDex,
    borrowToken,
    borrowAmount: signal.borrowAmount,
    minProfit: signal.minProfit,
    deadline: signal.deadline,
    signatureV: signal.v,
    signatureR: signal.r,
    signatureS: signal.s,
  };
}
