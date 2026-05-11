import { execSync } from "child_process";
import * as path from "path";

async function main() {
  console.log("\n" + "=".repeat(70));
  console.log(" FULL CONTRACT DEPLOYMENT TO 0G CHAIN");
  console.log("=".repeat(70) + "\n");

  const scriptsDir = path.dirname(__filename);
  const repoRoot = path.resolve(path.dirname(scriptsDir), "..");
  const network = process.env.HARDHAT_NETWORK || "zgTestnet";
  const deploymentOrder = [
    { name: "SignalValidator", file: "deploy_signal_validator.ts" },
    { name: "LendingPool", file: "deploy_lending_pool.ts" },
    { name: "ArbitrageExecutor", file: "deploy_arbitrage_executor.ts" },
  ];

  console.log("\nRunning inference replay validation before deployment...\n");
  try {
    const pythonBin = process.env.PYTHON_BIN || "python3";
    const validationOutput = execSync(
      `${pythonBin} ../tests/replay/replay_harness.py --ci-mode`,
      {
        cwd: path.join(repoRoot, "contracts"),
        encoding: "utf-8",
        stdio: ["ignore", "pipe", "pipe"],
      }
    );
    console.log(validationOutput);
  } catch (error) {
    console.error("\n❌ Inference validation failed; deployment blocked");
    console.error(error);
    process.exit(1);
  }

  const deployedAddresses: Record<string, string> = {};

  // Deploy in dependency order
  for (const contract of deploymentOrder) {
    console.log(
      `\n[${new Date().toISOString()}] Starting deployment of ${contract.name}...`
    );

    try {
      const output = execSync(
        `npx hardhat run scripts/${contract.file} --network ${network}`,
        {
          cwd: path.dirname(scriptsDir),
          encoding: "utf-8",
        }
      );

      console.log(output);

      // Extract address from output (simple pattern matching)
      const addressMatch = output.match(/Address: (0x[a-fA-F0-9]{40})/);
      if (addressMatch) {
        deployedAddresses[contract.name] = addressMatch[1];
      }
    } catch (error) {
      console.error(`\n❌ Failed to deploy ${contract.name}`);
      console.error(error);
      process.exit(1);
    }
  }

  // Summary
  console.log("\n" + "=".repeat(70));
  console.log(" DEPLOYMENT SUMMARY");
  console.log("=".repeat(70));

  for (const [contract, address] of Object.entries(deployedAddresses)) {
    console.log(`\n${contract}:`);
    console.log(`  Address: ${address}`);
    console.log(`  Explorer: https://chainscan-galileo.0g.ai/address/${address}`);
  }

  console.log("\n" + "=".repeat(70));
  console.log(" All contracts deployed successfully!");
  console.log(" Next steps:");
  console.log("  1. Verify contracts on 0G Explorer using deploy_verify.ts");
  console.log("  2. Update frontend configuration with contract addresses");
  console.log("  3. Run verification health check with verify_deployment.ts");
  console.log("=".repeat(70) + "\n");
}

main().catch((error) => {
  console.error("Deployment failed:", error);
  process.exit(1);
});
