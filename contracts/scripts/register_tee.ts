import { ethers } from "hardhat";
import * as fs from "fs";
import * as path from "path";

/**
 * Hardhat Script: Register TEE Key On-Chain
 * 
 * Automates the process of registering a new TEE public key on-chain after
 * the enclave boots and generates its key pair.
 * 
 * Prerequisites:
 *   - TEE_ETH_ADDRESS environment variable set (from enclave keystore)
 *   - TEE_MRENCLAVE environment variable set (from attestation)
 *   - SignalValidator contract already deployed
 *   - Deployer wallet has funds for gas
 * 
 * Usage:
 *   npx hardhat run scripts/register_tee.ts --network <network>
 * 
 * Output:
 *   - Prints transaction hash and Explorer link
 *   - Updates deployments/testnet.json with registration details
 */

async function registerTEE() {
  // Get environment variables
  const teeEthAddress = process.env.TEE_ETH_ADDRESS;
  const teeMrenclave = process.env.TEE_MRENCLAVE;
  const attestationType = process.env.TEE_ATTESTATION_TYPE || "SIMULATION";

  if (!teeEthAddress) {
    throw new Error("TEE_ETH_ADDRESS environment variable not set");
  }
  if (!teeMrenclave) {
    throw new Error("TEE_MRENCLAVE environment variable not set");
  }

  console.log("=".repeat(80));
  console.log("TEE Key Registration Script");
  console.log("=".repeat(80));
  console.log(`TEE Address: ${teeEthAddress}`);
  console.log(`MRENCLAVE: ${teeMrenclave}`);
  console.log(`Attestation Type: ${attestationType}`);

  // Get deployer signer
  const [deployer] = await ethers.getSigners();
  console.log(`Deployer Address: ${deployer.address}`);

  // Load deployment info
  const deploymentsPath = path.join(__dirname, "../deployments/testnet.json");
  if (!fs.existsSync(deploymentsPath)) {
    throw new Error(
      `Deployments file not found: ${deploymentsPath}\n` +
      `Run: npx hardhat run scripts/deploy_all.ts --network <network>`
    );
  }

  const deployments = JSON.parse(fs.readFileSync(deploymentsPath, "utf8"));
  const signalValidatorAddress = deployments.SignalValidator;

  if (!signalValidatorAddress) {
    throw new Error("SignalValidator address not found in deployments/testnet.json");
  }

  console.log(`SignalValidator Address: ${signalValidatorAddress}`);

  // Get SignalValidator contract
  const signalValidator = await ethers.getContractAt(
    "SignalValidator",
    signalValidatorAddress,
    deployer
  );

  // Prepare registration call
  const mrenclaveHex = teeMrenclave.startsWith("0x") ? teeMrenclave : `0x${teeMrenclave}`;
  const adminSignature = "0x"; // Empty for now; can be extended for additional security

  console.log("\nCalling registerTEE()...");

  try {
    const tx = await signalValidator.registerTEE(
      teeEthAddress,
      mrenclaveHex,
      attestationType,
      adminSignature,
      { gasLimit: 200000 }
    );

    console.log(`Transaction submitted: ${tx.hash}`);

    // Wait for confirmation
    const receipt = await tx.wait(1);
    console.log(`Transaction confirmed in block ${receipt?.blockNumber}`);

    // Get explorer link (adjust for network)
    const network = await ethers.provider.getNetwork();
    let explorerUrl = "";
    if (network.chainId === 16600n) {
      // 0G Testnet
      explorerUrl = `https://testnet.explorer.0g.ai/tx/${tx.hash}`;
    } else {
      explorerUrl = `https://etherscan.io/tx/${tx.hash}`;
    }

    console.log(`Explorer Link: ${explorerUrl}`);

    // Update deployments/testnet.json
    deployments.teeAddress = teeEthAddress;
    deployments.mrenclave = teeMrenclave;
    deployments.attestationType = attestationType;
    deployments.registeredAt = new Date().toISOString();
    deployments.registeredAtBlock = receipt?.blockNumber;
    deployments.registeredAtTxHash = tx.hash;

    fs.writeFileSync(
      deploymentsPath,
      JSON.stringify(deployments, null, 2)
    );

    console.log(`\nDeployments updated: ${deploymentsPath}`);
    console.log("=".repeat(80));
    console.log("TEE Registration Complete!");
    console.log("=".repeat(80));
    console.log("\nNext steps:");
    console.log("1. Verify TEE is active: npx hardhat run scripts/verify_tee.ts --network <network>");
    console.log("2. Start the inference agent: ./scripts/start_agent.sh");
    console.log("3. Monitor signals: tail -f logs/agent.log");

  } catch (error) {
    if (error instanceof Error) {
      console.error(`Registration failed: ${error.message}`);
    } else {
      console.error("Registration failed with unknown error");
    }
    process.exit(1);
  }
}

registerTEE()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
