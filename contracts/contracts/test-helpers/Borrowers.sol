// SPDX-License-Identifier: MIT
pragma solidity ^0.8.25;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "../LendingPool.sol";

/**
 * @title SimpleBorrower
 * @dev Simple test borrower that receives flashloan and repays
 */
contract SimpleBorrower is IERC3156FlashBorrower {
    address public lendingPool;
    IERC20 public borrowedToken;

    constructor() {}

    function onFlashLoan(
        address initiator,
        address token,
        uint256 amount,
        uint256 fee,
        bytes calldata data
    ) external override returns (bytes32) {
        // Store state for verification
        borrowedToken = IERC20(token);
        lendingPool = msg.sender;

        // Repay directly to lending pool
        uint256 repayAmount = amount + fee;
        borrowedToken.transfer(msg.sender, repayAmount);

        return keccak256("ERC3156FlashBorrower.onFlashLoan");
    }
}

/**
 * @title ShortRepaymentBorrower
 * @dev Borrower that intentionally underpays (minus 1 wei)
 */
contract ShortRepaymentBorrower is IERC3156FlashBorrower {
    IERC20 public token;
    address public pool;

    constructor(address _pool, address _token) {
        pool = _pool;
        token = IERC20(_token);
    }

    function onFlashLoan(
        address initiator,
        address token,
        uint256 amount,
        uint256 fee,
        bytes calldata data
    ) external override returns (bytes32) {
        // Repay with 1 wei short
        uint256 repayAmount = amount + fee - 1;
        IERC20(token).transfer(msg.sender, repayAmount);

        return keccak256("ERC3156FlashBorrower.onFlashLoan");
    }
}

/**
 * @title WrongHashBorrower
 * @dev Borrower that returns wrong callback hash
 */
contract WrongHashBorrower is IERC3156FlashBorrower {
    IERC20 public token;

    constructor(address _token) {
        token = IERC20(_token);
    }

    function onFlashLoan(
        address initiator,
        address token,
        uint256 amount,
        uint256 fee,
        bytes calldata data
    ) external override returns (bytes32) {
        // Repay correctly but return invalid callback hash
        uint256 repayAmount = amount + fee;
        IERC20(token).transfer(msg.sender, repayAmount);

        // Return wrong hash
        return keccak256("WrongHash");
    }
}

/**
 * @title ReentrantBorrower
 * @dev Borrower that attempts reentrancy attack
 */
contract ReentrantBorrower is IERC3156FlashBorrower {
    address public lendingPool;
    IERC20 public borrowedToken;
    bool public reentering;

    constructor(address _lendingPool) {
        lendingPool = _lendingPool;
    }

    function onFlashLoan(
        address initiator,
        address token,
        uint256 amount,
        uint256 fee,
        bytes calldata data
    ) external override returns (bytes32) {
        borrowedToken = IERC20(token);

        // Attempt reentrancy on first call
        if (!reentering) {
            reentering = true;
            // Try to call flashLoan again (will be blocked by ReentrancyGuard)
            IERC3156FlashLender(lendingPool).flashLoan(
                this,
                address(borrowedToken),
                amount,
                data
            );
        }

        // Repay (if reentrancy attempt is blocked)
        uint256 repayAmount = amount + fee;
        borrowedToken.transfer(msg.sender, repayAmount);

        return keccak256("ERC3156FlashBorrower.onFlashLoan");
    }
}
