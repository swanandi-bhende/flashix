import { ethers } from "hardhat";
import * as fs from "fs";
import * as path from "path";

async function main() {
  console.log("=".repeat(60));
  console.log("Deploying SignalValidator to 0G Chain...");
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

  // Get TEE signer address from environment
  const teeSigner = process.env.TEE_SIGNER_ADDRESS?.trim() || ethers.ZeroAddress;
  console.log(`TEE Signer Address: ${teeSigner}`);

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
  const existingSignalValidator = process.env.SIGNAL_VALIDATOR_ADDRESS?.trim();
  if (shouldReuseExisting && existingSignalValidator) {
    console.log(`\nReusing existing SignalValidator at: ${existingSignalValidator}`);
    return existingSignalValidator;
  }

  // Deploy SignalValidator
  console.log("\nDeploying SignalValidator contract...");
  const SignalValidator = await ethers.getContractFactory("SignalValidator");
  
  // Work around ethers.js v6 resolveName bug by manually encoding constructor args
  // Constructor takes: address _trustedSigner
  const abiCoder = ethers.AbiCoder.defaultAbiCoder();
  const encodedArgs = abiCoder.encode(["address"], [teeSigner]);
  const deployData = SignalValidator.bytecode + encodedArgs.slice(2);
  
  console.log("Sending deployment transaction...");
  const tx = await deployer.sendTransaction({
    data: deployData,
    gasLimit: 2000000,  // Set explicit gas limit to bypass estimation
  });
  
  console.log(`Tx sent: ${tx.hash}`);
  const receipt = await tx.wait(2);
  
  if (!receipt || !receipt.contractAddress) {
    throw new Error("Deployment failed: no contract address in receipt");
  }
  
  const signalValidatorAddr = receipt.contractAddress;
  const signalValidator = SignalValidator.attach(signalValidatorAddr);

  const txHash = tx.hash;
  const blockNumber = receipt.blockNumber || 0;
  const gasUsed = receipt.gasUsed?.toString() || "0";

  console.log(`\n✓ SignalValidator deployed successfully!`);
  console.log(`  Address: ${signalValidatorAddr}`);
  console.log(`  Transaction: ${txHash}`);
  console.log(`  Block: ${blockNumber}`);
  console.log(`  Gas Used: ${gasUsed}`);
  console.log(`  TEE Signer: ${teeSigner}`);

  // Save to ABI folder
  const abiDir = path.join(__dirname, "../abi");
  if (!fs.existsSync(abiDir)) {
    fs.mkdirSync(abiDir, { recursive: true });
  }

  const artifactPath = path.join(
    __dirname,
    "../artifacts/contracts/SignalValidator.sol/SignalValidator.json"
  );
  const artifact = JSON.parse(fs.readFileSync(artifactPath, "utf-8"));

  const contractData = {
    address: signalValidatorAddr,
    abi: artifact.abi,
    chainId,
    deployedAt: new Date().toISOString(),
    txHash: txHash,
    blockNumber: blockNumber,
    teeSigner,
  };

  fs.writeFileSync(
    path.join(abiDir, "SignalValidator.json"),
    JSON.stringify(contractData, null, 2)
  );

  console.log(`  ABI saved to: /abi/SignalValidator.json`);

  // Update .env
  const envPath = path.join(__dirname, "../.env");
  let envContent = fs.existsSync(envPath) ? fs.readFileSync(envPath, "utf-8") : "";

  if (envContent.includes("SIGNAL_VALIDATOR_ADDRESS")) {
    envContent = envContent.replace(
      /SIGNAL_VALIDATOR_ADDRESS=.*/,
      `SIGNAL_VALIDATOR_ADDRESS=${signalValidatorAddr}`
    );
  } else {
    envContent += `SIGNAL_VALIDATOR_ADDRESS=${signalValidatorAddr}\n`;
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

  const teeSigner2 = process.env.TEE_SIGNER_ADDRESS?.trim() || null;
  deployments.deployedAt = new Date().toISOString();
  deployments.contracts = deployments.contracts || {};
  deployments.contracts.SignalValidator = {
    ...(deployments.contracts.SignalValidator || {}),
    address: signalValidatorAddr,
    txHash,
    blockNumber,
    gasUsed,
    trustedSigner: teeSigner2,
    verified: false,
    explorerUrl: `${explorerBase}/address/${signalValidatorAddr}`,
    verificationUrl: null,
  };
  fs.writeFileSync(deploymentsPath, JSON.stringify(deployments, null, 2));
  console.log(`  deployments/${chainId === 16661 ? "mainnet.json" : "testnet.json"} updated`);

  console.log("\n" + "=".repeat(60));
  console.log("SignalValidator deployment complete!");
  console.log("=".repeat(60));

  return signalValidatorAddr;
}

main().catch((error) => {
  console.error("Deployment failed:", error);
  process.exitCode = 1;
});
