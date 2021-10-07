import ethers, { constants, Wallet, utils, BigNumber } from 'ethers';
import { latency, bigNumberWithDecimalToStr } from '../../services/base';
import { GatewayError } from '../../services/error-handler';
import { EthereumBase, Token } from '../../services/ethereum-base';

export async function approve(
  ethereum: EthereumBase,
  spender: string,
  privateKey: string,
  token: string,
  amount?: BigNumber | string,
  nonce?: number
) {
  const initTime = Date.now();
  let wallet: Wallet;
  try {
    wallet = ethereum.getWallet(privateKey);
  } catch (err) {
    throw new Error(`Error getting wallet ${err}`);
  }
  const fullToken = ethereum.getTokenBySymbol(token);
  if (!fullToken) {
    throw new Error(`Token "${token}" is not supported`);
  }
  amount = amount
    ? utils.parseUnits(amount.toString(), fullToken.decimals)
    : constants.MaxUint256;

  // call approve function

  const approval = await ethereum.approveERC20(
    wallet,
    spender,
    fullToken.address,
    amount,
    nonce
  );

  return {
    timestamp: initTime,
    latency: latency(initTime, Date.now()),
    tokenAddress: fullToken.address,
    spender: spender,
    amount: bigNumberWithDecimalToStr(amount, fullToken.decimals),
    nonce: approval.nonce,
    approval: approval,
  };
}

// TransactionReceipt from ethers uses BigNumber which is not easy to interpret directly from JSON.
// Transform those BigNumbers to string and pass the rest of the data without changes.

export interface EthereumTransactionReceipt
  extends Omit<
    ethers.providers.TransactionReceipt,
    'gasUsed' | 'cumulativeGasUsed'
  > {
  gasUsed: string;
  cumulativeGasUsed: string;
}

const toEthereumTransactionReceipt = (
  receipt: ethers.providers.TransactionReceipt | null
): EthereumTransactionReceipt | null => {
  if (receipt) {
    return {
      ...receipt,
      gasUsed: receipt.gasUsed.toString(),
      cumulativeGasUsed: receipt.cumulativeGasUsed.toString(),
    };
  }

  return null;
};

export async function poll(ethereum: EthereumBase, txHash: string) {
  const initTime = Date.now();
  const receipt = await ethereum.getTransactionReceipt(txHash);
  const confirmed = !!receipt && !!receipt.blockNumber;

  if (receipt && receipt.status === 0) {
    const transaction = await ethereum.getTransaction(txHash);
    const gasUsed = BigNumber.from(receipt.gasUsed).toNumber();
    const gasLimit = BigNumber.from(transaction.gasLimit).toNumber();
    if (gasUsed / gasLimit > 0.9)
      throw new GatewayError(503, 1003, 'Transaction out of gas.');
  }

  return {
    timestamp: initTime,
    latency: latency(initTime, Date.now()),
    txHash,
    confirmed,
    receipt: toEthereumTransactionReceipt(receipt),
  };
}

export function getTokenSymbolsToTokens(
  ethereum: EthereumBase,
  tokenSymbols: Array<string>
): Record<string, Token> {
  const tokens: Record<string, Token> = {};

  for (let i = 0; i < tokenSymbols.length; i++) {
    const symbol = tokenSymbols[i];
    const token = ethereum.getTokenBySymbol(symbol);
    if (!token) {
      continue;
    }

    tokens[symbol] = token;
  }

  return tokens;
}
