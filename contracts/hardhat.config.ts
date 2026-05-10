import { HardhatUserConfig } from "hardhat/config";
import "@nomicfoundation/hardhat-toolbox";
import "@nomicfoundation/hardhat-verify";
import "solidity-coverage";
import "dotenv/config";

const rawDeployerPrivateKey = process.env.DEPLOYER_PRIVATE_KEY?.trim() || "";
const normalizedDeployerPrivateKey =
  rawDeployerPrivateKey === ""
    ? ""
    : rawDeployerPrivateKey.startsWith("0x")
      ? rawDeployerPrivateKey
      : `0x${rawDeployerPrivateKey}`;

const isValidPrivateKey =
  /^0x[0-9a-fA-F]{64}$/.test(normalizedDeployerPrivateKey) &&
  !/^0x0{64}$/.test(normalizedDeployerPrivateKey);

const DEPLOYER_ACCOUNTS = isValidPrivateKey ? [normalizedDeployerPrivateKey] : [];

const config: HardhatUserConfig = {
  solidity: {
    version: "0.8.35",
    settings: {
      optimizer: {
        enabled: true,
        runs: 200,
      },
      evmVersion: "cancun",
    },
  },
  networks: {
    hardhat: {
      allowUnlimitedContractSize: true,
    },
    localhost: {
      url: "http://127.0.0.1:8545",
    },
    // 0G Chain Testnet
    zgTestnet: {
      url: "https://evmrpc-testnet.0g.ai",
      chainId: 16602,
      accounts: DEPLOYER_ACCOUNTS,
      gasPrice: "auto",
    },
    // 0G Chain Mainnet
    zgMainnet: {
      url: "https://evmrpc.0g.ai",
      chainId: 16600,
      accounts: DEPLOYER_ACCOUNTS,
      gasPrice: "auto",
    },
  },
  etherscan: {
    apiKey: {
      zgTestnet: process.env.BLOCK_EXPLORER_API_KEY || "",
    },
    customChains: [
      {
        network: "zgTestnet",
        chainId: 16602,
        urls: {
          apiURL: "https://chainscan-galileo.0g.ai/api",
          browserURL: "https://chainscan-galileo.0g.ai",
        },
      },
    ],
  },
  paths: {
    sources: "./contracts",
    tests: "./tests",
    cache: "./cache",
    artifacts: "./artifacts",
  },
  typechain: {
    outDir: "typechain-types",
    target: "ethers-v6",
  },
};

export default config;
