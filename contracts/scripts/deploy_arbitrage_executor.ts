import { ethers } from "hardhat";
import * as fs from "fs";
import * as path from "path";

async function main() {
  console.log("=".repeat(60));
  console.log("Deploying ArbitrageExecutor to 0G Chain...");
  console.log("=".repeat(60));

  // Get deployer
  const signers = await ethers.getSigners();
  if (signers.length === 0) {
    throw new Error(
      "No deployer account available. Set DEPLOYER_PRIVATE_KEY in contracts/.env with a valid funded key."
    );
  }
  const [deployer] = signers;
  const deployerAddr = await deployer.getAddress();
  const network = await ethers.provider.getNetwork();
  const chainId = Number(network.chainId);
  const networkLabel = chainId === 16661 ? "zgMainnet" : "zgTestnet";
  const explorerBase =
    chainId === 16661 ? "https://chainscan.0g.ai" : "https://chainscan-galileo.0g.ai";
  console.log(`\nDeployer address: ${deployerAddr}`);

  // Get profit recipient from environment or use deployer
  let profitRecipient = process.env.PROFIT_RECIPIENT_ADDRESS || deployerAddr;
  console.log(`Profit recipient address: ${profitRecipient}`);

  // Check deployer balance
  const balance = await ethers.provider.getBalance(deployerAddr);
  const minRequired = ethers.parseEther("0.1");
  console.log(`Deployer balance: ${ethers.formatEther(balance)} ETH`);

  if (balance < minRequired) {
    throw new Error(
      `Insufficient balance. Required: ${ethers.formatEther(minRequired)} ETH, Got: ${ethers.formatEther(balance)} ETH`
    );
  }

  // Deploy ArbitrageExecutor
  console.log("\nDeploying ArbitrageExecutor contract...");
  const ArbitrageExecutor = await ethers.getContractFactory("ArbitrageExecutor");
  
  // Work around ethers.js v6 resolveName bug by manually encoding constructor args
  // Constructor takes: address _profitRecipient
  const abiCoder = ethers.AbiCoder.defaultAbiCoder();
  const encodedArgs = abiCoder.encode(["address"], [profitRecipient]);
  const deployData = ArbitrageExecutor.bytecode + encodedArgs.slice(2);
  
  console.log("Sending deployment transaction...");
  const tx = await deployer.sendTransaction({
    data: deployData,
    gasLimit: 3000000,  // Set explicit gas limit
  });
  
  console.log(`Tx sent: ${tx.hash}`);
  const receipt = await tx.wait(2);
  
  if (!receipt || !receipt.contractAddress) {
    throw new Error("Deployment failed: no contract address in receipt");
  }
  
  const arbitrageExecutorAddr = receipt.contractAddress;
  const arbitrageExecutor = ArbitrageExecutor.attach(arbitrageExecutorAddr);
  const txHash = tx.hash;
  const blockNumber = receipt.blockNumber || 0;
  const gasUsed = receipt.gasUsed?.toString() || "0";

  console.log(`\n✓ ArbitrageExecutor deployed successfully!`);
  console.log(`  Address: ${arbitrageExecutorAddr}`);
  console.log(`  Transaction: ${txHash}`);
  console.log(`  Block: ${blockNumber}`);
  console.log(`  Gas Used: ${gasUsed}`);
  console.log(`  Profit Recipient: ${profitRecipient}`);

  // Get deployed contract addresses from .env or use provided addresses
  const envPath = path.join(__dirname, "../.env");
  let envContent = fs.existsSync(envPath) ? fs.readFileSync(envPath, "utf-8") : "";

  // Extract addresses from .env
  const lendingPoolMatch = envContent.match(/LENDING_POOL_ADDRESS=(.+)/);
  const signalValidatorMatch = envContent.match(/SIGNAL_VALIDATOR_ADDRESS=(.+)/);

  const lendingPoolAddr = lendingPoolMatch
    ? lendingPoolMatch[1].trim()
    : process.env.LENDING_POOL_ADDRESS;
  const signalValidatorAddr = signalValidatorMatch
    ? signalValidatorMatch[1].trim()
    : process.env.SIGNAL_VALIDATOR_ADDRESS;

  if (!lendingPoolAddr) {
    console.warn(
      "Warning: LENDING_POOL_ADDRESS not found. Please deploy LendingPool first."
    );
  }

  if (!signalValidatorAddr) {
    console.warn(
      "Warning: SIGNAL_VALIDATOR_ADDRESS not found. Please deploy SignalValidator first."
    );
  }

  // Save to ABI folder
  const abiDir = path.join(__dirname, "../abi");
  if (!fs.existsSync(abiDir)) {
    fs.mkdirSync(abiDir, { recursive: true });
  }

  const artifactPath = path.join(
    __dirname,
    "../artifacts/contracts/ArbitrageExecutor.sol/ArbitrageExecutor.json"
  );
  const artifact = JSON.parse(fs.readFileSync(artifactPath, "utf-8"));

  const contractData = {
    address: arbitrageExecutorAddr,
    abi: artifact.abi,
    chainId,
    deployedAt: new Date().toISOString(),
    txHash: txHash,
    blockNumber: blockNumber,
    profitRecipient: profitRecipient,
    lendingPool: lendingPoolAddr,
    signalValidator: signalValidatorAddr,
  };

  fs.writeFileSync(
    path.join(abiDir, "ArbitrageExecutor.json"),
    JSON.stringify(contractData, null, 2)
  );

  console.log(`  ABI saved to: /abi/ArbitrageExecutor.json`);

  // Update .env
  if (envContent.includes("ARBITRAGE_EXECUTOR_ADDRESS")) {
    envContent = envContent.replace(
      /ARBITRAGE_EXECUTOR_ADDRESS=.*/,
      `ARBITRAGE_EXECUTOR_ADDRESS=${arbitrageExecutorAddr}`
    );
  } else {
    envContent += `ARBITRAGE_EXECUTOR_ADDRESS=${arbitrageExecutorAddr}\n`;
  }

  fs.writeFileSync(envPath, envContent);
  console.log(`  .env updated`);

  // Update deployments manifest
  const deploymentsDir = path.join(__dirname, "../deployments");
  const deploymentsPath = path.join(
    deploymentsDir,
    chainId === 16661 ? "mainnet.json" : "testnet.json"
  );
  if (!fs.existsSync(deploymentsDir)) {
    fs.mkdirSync(deploymentsDir, { recursive: true });
  }

  const deployments = fs.existsSync(deploymentsPath)
    ? JSON.parse(fs.readFileSync(deploymentsPath, "utf-8"))
    : {
        network: networkLabel,
        chainId,
        deployedAt: null,
        contracts: {},
      };

  deployments.deployedAt = new Date().toISOString();
  deployments.contracts = deployments.contracts || {};
  deployments.contracts.ArbitrageExecutor = {
    ...(deployments.contracts.ArbitrageExecutor || {}),
    address: arbitrageExecutorAddr,
    txHash,
    blockNumber,
    gasUsed,
    profitRecipient: profitRecipient,
    lendingPool: lendingPoolAddr,
    signalValidator: signalValidatorAddr,
    verified: false,
    explorerUrl: `${explorerBase}/address/${arbitrageExecutorAddr}`,
    verificationUrl: null,
  };
  fs.writeFileSync(deploymentsPath, JSON.stringify(deployments, null, 2));
  console.log(`  deployments/${chainId === 16661 ? "mainnet.json" : "testnet.json"} updated`);

  console.log("\n" + "=".repeat(60));
  console.log("ArbitrageExecutor deployment complete!");
  console.log("=".repeat(60));

  return arbitrageExecutorAddr;
}

main().catch((error) => {
  console.error("Deployment failed:", error);
  process.exitCode = 1;
});
