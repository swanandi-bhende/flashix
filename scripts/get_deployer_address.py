import os
from eth_account import Account

def main():
    key = os.environ.get("DEPLOYER_PRIVATE_KEY")
    if not key:
        raise SystemExit("DEPLOYER_PRIVATE_KEY not set in environment")
    if key.startswith('0x'):
        key = key[2:]
    acct = Account.from_key(key)
    print(acct.address)

if __name__ == '__main__':
    main()
