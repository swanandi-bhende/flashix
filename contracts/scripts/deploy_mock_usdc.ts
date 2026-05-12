import { ethers } from "hardhat";

async function main() {
  const [deployer] = await ethers.getSigners();
  console.log(`Deploying MockUSDC from: ${deployer.address}`);

  // Deploy MockUSDC
  const MockUSDC = await ethers.getContractFactory("MockUSDC");
  const usdc = await MockUSDC.deploy();
  await usdc.waitForDeployment();
  
  const usdcAddress = await usdc.getAddress();
  console.log(`✓ MockUSDC deployed at: ${usdcAddress}`);

  // Mint 10000 USDC to deployer
  const mintAmount = ethers.parseUnits("10000", 6);
  const mintTx = await usdc.mint(deployer.address, mintAmount);
  await mintTx.wait();
  console.log(`✓ Minted ${ethers.formatUnits(mintAmount, 6)} MockUSDC to deployer`);

  // Get balance
  const balance = await usdc.balanceOf(deployer.address);
  console.log(`Deployer balance: ${ethers.formatUnits(balance, 6)} USDC`);

  console.log(`\nAdd to .env:`);
  console.log(`USDC_ADDRESS=${usdcAddress}`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
