import { ethers } from "hardhat";
import * as fs from "fs";
import * as path from "path";

async function main() {
  console.log("=".repeat(60));
  console.log("Testing SignalValidatorSimple deployment...");
  console.log("=".repeat(60));

  const signers = await ethers.getSigners();
  if (signers.length === 0) {
    throw new Error("No deployer account available.");
  }
  const [deployer] = signers;
  const deployerAddr = await deployer.getAddress();
  console.log(`\nDeployer address: ${deployerAddr}`);

  const balance = await ethers.provider.getBalance(deployerAddr);
  console.log(`Deployer balance: ${ethers.formatEther(balance)} ETH`);

  const expectedMrenclave = ethers.ZeroHash;
  console.log(`Expected MRENCLAVE: ${expectedMrenclave}`);

  // Deploy using manual transaction
  const SignalValidatorSimple = await ethers.getContractFactory("SignalValidatorSimple");
  const abiCoder = ethers.AbiCoder.defaultAbiCoder();
  const encodedArgs = abiCoder.encode(["bytes32"], [expectedMrenclave]);
  const deployData = SignalValidatorSimple.bytecode + encodedArgs.slice(2);
  
  console.log("\nSending deployment transaction...");
  const tx = await deployer.sendTransaction({
    data: deployData,
  });
  
  console.log(`Tx sent: ${tx.hash}`);
  const receipt = await tx.wait(2);
  
  if (!receipt || !receipt.contractAddress) {
    throw new Error("Deployment failed: no contract address in receipt");
  }
  
  const contractAddr = receipt.contractAddress;
  console.log(`\n✓ SignalValidatorSimple deployed successfully!`);
  console.log(`  Address: ${contractAddr}`);
  console.log(`  Transaction: ${tx.hash}`);
  console.log(`  Block: ${receipt.blockNumber}`);
  console.log(`  Gas Used: ${receipt.gasUsed}`);

  return contractAddr;
}

main().catch((error) => {
  console.error("Deployment failed:", error);
  process.exitCode = 1;
});
