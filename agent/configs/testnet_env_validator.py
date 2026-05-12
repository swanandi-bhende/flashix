import json
import os
from web3 import Web3
from dotenv import load_dotenv

load_dotenv()

class TestnetConfigurationError(Exception):
    pass

REQUIRED_CONTRACT_KEYS = [
    'signalValidator', 'lendingPool', 'arbitrageExecutorV2'
]

def validate(deployments_path='deployments/testnet.json'):
    if not os.path.exists(deployments_path):
        raise TestnetConfigurationError(f"Missing deployments file: {deployments_path}")
    with open(deployments_path, 'r') as f:
        data = json.load(f)

    rpc = os.environ.get('ZG_TESTNET_RPC')
    if not rpc:
        raise TestnetConfigurationError('ZG_TESTNET_RPC not set')
    w3 = Web3(Web3.HTTPProvider(rpc))

    for k in REQUIRED_CONTRACT_KEYS:
        addr = data.get(k)
        if not addr:
            raise TestnetConfigurationError(f"Missing contract address for {k}")
        code = w3.eth.get_code(addr)
        if not code or code == b"":
            raise TestnetConfigurationError(f"No bytecode at address {addr} for {k}")

    # check lending pool has >= 100 USDC by checking balance directly
    lp = data.get('lendingPool')
    usdc_addr = os.environ.get('USDC_ADDRESS')
    if not usdc_addr:
        raise TestnetConfigurationError('USDC_ADDRESS not set in env')

    try:
        # Use balanceOf to check USDC balance in lending pool
        abi = [{"constant":True,"inputs":[{"name":"account","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"payable":False,"stateMutability":"view","type":"function"}]
        contract = w3.eth.contract(address=usdc_addr, abi=abi)
        pool_balance = contract.functions.balanceOf(lp).call()
        if pool_balance < 100 * 10**6:
            raise TestnetConfigurationError(f"LendingPool USDC balance below 100 USDC: {pool_balance}")
    except TestnetConfigurationError:
        raise
    except Exception as e:
        raise TestnetConfigurationError(f"Error checking lending pool balance: {e}")

    return True

if __name__ == '__main__':
    try:
        validate()
        print('TESTNET_ENV_VALIDATION: OK')
    except TestnetConfigurationError as e:
        print('TESTNET_ENV_VALIDATION: FAIL', e)
        raise SystemExit(1)
