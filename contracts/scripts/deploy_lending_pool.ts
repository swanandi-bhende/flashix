import { ethers } from "hardhat";
import * as fs from "fs";
import * as path from "path";

async function main() {
  console.log("=".repeat(60));
  console.log("Deploying LendingPool to 0G Chain...");
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

  // Check deployer balance
  const balance = await ethers.provider.getBalance(deployerAddr);
  const minRequired = ethers.parseEther("0.1");
  console.log(`Deployer balance: ${ethers.formatEther(balance)} ETH`);

  if (balance < minRequired) {
    throw new Error(
      `Insufficient balance. Required: ${ethers.formatEther(minRequired)} ETH, Got: ${ethers.formatEther(balance)} ETH`
    );
  }

  // Safety default: force fresh deployments unless explicitly set to true.
  const shouldReuseExisting = process.env.REUSE_DEPLOYED_CONTRACTS === "true";
  const existingLendingPool = process.env.LENDING_POOL_ADDRESS?.trim();
  if (shouldReuseExisting && existingLendingPool) {
    console.log(`\nReusing existing LendingPool at: ${existingLendingPool}`);
    return existingLendingPool;
  }

  // Deploy LendingPool
  console.log("\nDeploying LendingPool contract...");
  const LendingPool = await ethers.getContractFactory("LendingPool");
  const lendingPool = await LendingPool.deploy();

  const deploymentTx = lendingPool.deploymentTransaction();
  await lendingPool.waitForDeployment();
  const receipt = await deploymentTx?.wait(2);

  const lendingPoolAddr = await lendingPool.getAddress();
  const txHash = deploymentTx?.hash || "";
  const blockNumber = receipt?.blockNumber || 0;
  const gasUsed = receipt?.gasUsed?.toString() || "0";
  console.log(`\n✓ LendingPool deployed successfully!`);
  console.log(`  Address: ${lendingPoolAddr}`);
  console.log(`  Transaction: ${txHash}`);
  console.log(`  Block: ${blockNumber}`);
  console.log(`  Gas Used: ${gasUsed}`);

  // Save to ABI folder
  const abiDir = path.join(__dirname, "../abi");
  if (!fs.existsSync(abiDir)) {
    fs.mkdirSync(abiDir, { recursive: true });
  }

  const artifactPath = path.join(
    __dirname,
    "../artifacts/contracts/LendingPool.sol/LendingPool.json"
  );
  const artifact = JSON.parse(fs.readFileSync(artifactPath, "utf-8"));

  const contractData = {
    address: lendingPoolAddr,
    abi: artifact.abi,
    chainId,
    deployedAt: new Date().toISOString(),
    txHash: txHash,
    blockNumber: blockNumber,
  };

  fs.writeFileSync(
    path.join(abiDir, "LendingPool.json"),
    JSON.stringify(contractData, null, 2)
  );

  console.log(`  ABI saved to: /abi/LendingPool.json`);

  // Update .env
  const envPath = path.join(__dirname, "../.env");
  let envContent = fs.existsSync(envPath) ? fs.readFileSync(envPath, "utf-8") : "";

  if (envContent.includes("LENDING_POOL_ADDRESS")) {
    envContent = envContent.replace(
      /LENDING_POOL_ADDRESS=.*/,
      `LENDING_POOL_ADDRESS=${lendingPoolAddr}`
    );
  } else {
    envContent += `LENDING_POOL_ADDRESS=${lendingPoolAddr}\n`;
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
  deployments.contracts.LendingPool = {
    ...(deployments.contracts.LendingPool || {}),
    address: lendingPoolAddr,
    txHash,
    blockNumber,
    gasUsed,
    verified: false,
    explorerUrl: `${explorerBase}/address/${lendingPoolAddr}`,
    verificationUrl: null,
  };
  fs.writeFileSync(deploymentsPath, JSON.stringify(deployments, null, 2));
  console.log(`  deployments/${chainId === 16661 ? "mainnet.json" : "testnet.json"} updated`);

  console.log("\n" + "=".repeat(60));
  console.log("LendingPool deployment complete!");
  console.log("=".repeat(60));

  return lendingPoolAddr;
}

main().catch((error) => {
  console.error("Deployment failed:", error);
  process.exitCode = 1;
});
