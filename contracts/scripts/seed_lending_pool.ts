import { ethers } from "hardhat";

const LENDING_POOL = "0xCe233f627834e017097feFB53f4dfD2085A9B988";
const USDC = "0xeC83852Ae89B7d5D1dDc8722e043A81AD8359f35";
const AMOUNT = ethers.parseUnits("500", 6); // 500 USDC (6 decimals)

async function main() {
  const [deployer] = await ethers.getSigners();
  console.log(`Seeding lending pool from: ${deployer.address}`);

  // Get USDC contract
  const usdcABI = [
    "function balanceOf(address) public view returns (uint256)",
    "function approve(address spender, uint256 amount) public returns (bool)",
    "function transfer(address to, uint256 amount) public returns (bool)",
  ];

  const usdc = new ethers.Contract(USDC, usdcABI, deployer);

  // Check balance
  const balance = await usdc.balanceOf(deployer.address);
  console.log(`Deployer USDC balance: ${ethers.formatUnits(balance, 6)} USDC`);

  if (balance < AMOUNT) {
    console.error(`❌ Insufficient USDC. Need ${ethers.formatUnits(AMOUNT, 6)}, have ${ethers.formatUnits(balance, 6)}`);
    process.exit(1);
  }

  // Approve lending pool
  console.log("Approving lending pool to receive USDC...");
  const approveTx = await usdc.approve(LENDING_POOL, AMOUNT);
  await approveTx.wait();
  console.log(`✓ Approval tx: ${approveTx.hash}`);

  // Transfer USDC to lending pool
  console.log(`Transferring ${ethers.formatUnits(AMOUNT, 6)} USDC to lending pool...`);
  const transferTx = await usdc.transfer(LENDING_POOL, AMOUNT);
  const receipt = await transferTx.wait();
  console.log(`✓ Transfer tx: ${transferTx.hash}`);

  // Verify balance
  const poolBalance = await usdc.balanceOf(LENDING_POOL);
  console.log(`\n✅ Lending pool USDC balance: ${ethers.formatUnits(poolBalance, 6)} USDC`);
  console.log(`Deployment ready for testnet validation.`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
