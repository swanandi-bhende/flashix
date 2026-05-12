import os
import argparse
from web3 import Web3
from dotenv import load_dotenv

load_dotenv()

def get_balance(rpc_url, address):
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    return w3.eth.get_balance(address)

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--min-eth', type=float, required=True)
    args = p.parse_args()

    rpc = os.environ.get('ZG_TESTNET_RPC')
    if not rpc:
        raise SystemExit('ZG_TESTNET_RPC not set')
    priv = os.environ.get('DEPLOYER_PRIVATE_KEY')
    if not priv:
        raise SystemExit('DEPLOYER_PRIVATE_KEY not set')
    from eth_account import Account
    pk = priv
    if pk.startswith('0x'):
        pk = pk[2:]
    acct = Account.from_key(pk)
    bal = get_balance(rpc, acct.address)
    eth_bal = Web3.from_wei(bal, 'ether')
    print(f"Address: {acct.address} balance={eth_bal} ETH")
    if eth_bal < args.min_eth:
        raise SystemExit(f"Balance {eth_bal} < required {args.min_eth}")
    return 0

if __name__ == '__main__':
    main()
