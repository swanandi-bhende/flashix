import { ethers } from "hardhat";
import * as fs from "fs";
import * as path from "path";

async function main() {
  console.log("=".repeat(70));
  console.log(" DEPLOYMENT VERIFICATION");
  console.log("=".repeat(70));

  const abiDir = path.join(__dirname, "../abi");
  const envPath = path.join(__dirname, "../.env");

  // Load environment
  if (fs.existsSync(envPath)) {
    const envContent = fs.readFileSync(envPath, "utf-8");
    const lines = envContent.split("\n");
    for (const line of lines) {
      const [key, value] = line.split("=");
      if (key && value) {
        process.env[key.trim()] = value.trim();
      }
    }
  }

  const contracts = [
    { name: "LendingPool", envVar: "LENDING_POOL_ADDRESS" },
    { name: "SignalValidator", envVar: "SIGNAL_VALIDATOR_ADDRESS" },
    { name: "ArbitrageExecutor", envVar: "ARBITRAGE_EXECUTOR_ADDRESS" },
  ];

  let allHealthy = true;

  console.log("\nVerifying deployed contracts...\n");

  for (const contract of contracts) {
    const address = process.env[contract.envVar];

    if (!address) {
      console.log(`❌ ${contract.name}: NOT DEPLOYED (${contract.envVar} not set)`);
      allHealthy = false;
      continue;
    }

    try {
      // Load ABI
      const abiPath = path.join(abiDir, `${contract.name}.json`);
      if (!fs.existsSync(abiPath)) {
        console.log(`❌ ${contract.name}: ABI NOT FOUND at ${abiPath}`);
        allHealthy = false;
        continue;
      }

      const abiData = JSON.parse(fs.readFileSync(abiPath, "utf-8"));
      const contractInstance = new ethers.Contract(
        address,
        abiData.abi,
        ethers.provider
      );

      // Try to call a read-only function based on contract type
      let isHealthy = false;
      let responseData = "";

      if (contract.name === "LendingPool") {
        // Try to read FEE_BPS constant
        try {
          const feeBps = await contractInstance.FEE_BPS();
          responseData = `FEE_BPS = ${feeBps}`;
          isHealthy = true;
        } catch (e) {
          responseData = `Error reading FEE_BPS: ${(e as Error).message}`;
        }
      } else if (contract.name === "SignalValidator") {
        // Try to read trusted signer
        try {
          const signer = await contractInstance.getTrustedSigner();
          responseData = `Trusted Signer = ${signer}`;
          isHealthy = true;
        } catch (e) {
          responseData = `Error reading trusted signer: ${(e as Error).message}`;
        }
      } else if (contract.name === "ArbitrageExecutor") {
        // Try to read execution counter
        try {
          const count = await contractInstance.getExecutionCount();
          responseData = `Execution Count = ${count}`;
          isHealthy = true;
        } catch (e) {
          responseData = `Error reading execution count: ${(e as Error).message}`;
        }
      }

      if (isHealthy) {
        console.log(`✓ ${contract.name}`);
        console.log(`  Address: ${address}`);
        console.log(`  Status: RESPONSIVE`);
        console.log(`  Response: ${responseData}`);
        console.log(
          `  Explorer: https://chainscan-galileo.0g.ai/address/${address}`
        );
      } else {
        console.log(`⚠ ${contract.name}`);
        console.log(`  Address: ${address}`);
        console.log(`  Status: NOT RESPONSIVE`);
        console.log(`  Error: ${responseData}`);
        allHealthy = false;
      }
    } catch (error) {
      console.log(`❌ ${contract.name}`);
      console.log(`  Address: ${address}`);
      console.log(`  Status: ERROR`);
      console.log(`  Error: ${(error as Error).message}`);
      allHealthy = false;
    }

    console.log("");
  }

  console.log("=".repeat(70));
  if (allHealthy) {
    console.log(" ✓ ALL CONTRACTS VERIFIED SUCCESSFULLY");
    console.log(" Deployment is ready for production use!");
  } else {
    console.log(" ⚠ SOME CONTRACTS FAILED VERIFICATION");
    console.log(" Please check the errors above.");
  }
  console.log("=".repeat(70));

  process.exit(allHealthy ? 0 : 1);
}

main().catch((error) => {
  console.error("Verification failed:", error);
  process.exitCode = 1;
});
