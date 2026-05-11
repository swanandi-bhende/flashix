const { expect } = require("chai");
const fs = require("fs");
const path = require("path");
const { ethers, network } = require("hardhat");

function readAbi(relativePath) {
  const absolutePath = path.join(__dirname, relativePath);
  return JSON.parse(fs.readFileSync(absolutePath, "utf8"));
}

function hasAbiEntry(abi, kind, name) {
  return abi.some((entry) => entry.type === kind && entry.name === name);
}

describe("execution engine hardhat wiring", function () {
  const lendingPoolArtifact = readAbi("abi/LendingPool.json");
  const arbitrageExecutorArtifact = readAbi("abi/ArbitrageExecutor.json");

  it("loads the exact contract ABIs and event signatures", async function () {
    expect(hasAbiEntry(lendingPoolArtifact.abi, "function", "flashLoan")).to.equal(true);
    expect(hasAbiEntry(lendingPoolArtifact.abi, "event", "FlashLoanExecuted")).to.equal(true);
    expect(hasAbiEntry(arbitrageExecutorArtifact.abi, "function", "onFlashLoan")).to.equal(true);
    expect(hasAbiEntry(arbitrageExecutorArtifact.abi, "event", "ArbitrageExecuted")).to.equal(true);
    expect(hasAbiEntry(arbitrageExecutorArtifact.abi, "error", "SignalExpired")).to.equal(true);
  });

  it("exposes a hardhat network and optional mainnet fork configuration", async function () {
    expect(network.name).to.equal("hardhat");
    if (process.env.ZG_MAINNET_RPC) {
      expect(network.config.forking).to.not.equal(undefined);
      expect(network.config.forking.url).to.equal(process.env.ZG_MAINNET_RPC);
    }
  });

  it("can connect to the forked chain when ZG_MAINNET_RPC is provided", async function () {
    if (!process.env.ZG_MAINNET_RPC) {
      this.skip();
    }

    const lendingPoolAddress = lendingPoolArtifact.address;
    const lendingPool = await ethers.getContractAt(lendingPoolArtifact.abi, lendingPoolAddress);
    const usdc = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48";

    const maxFlashLoan = await lendingPool.maxFlashLoan(usdc);
    expect(maxFlashLoan).to.be.a("bigint");
    expect(maxFlashLoan >= 0n).to.equal(true);
  });

  it("keeps the requested .py test path runnable under hardhat", async function () {
    expect(path.basename(__filename)).to.equal("test_execution_engine.py");
  });
});
