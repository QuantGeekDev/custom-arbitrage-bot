import { TokenListType } from '../../services/base';

export namespace EthereumConfig {
  export interface NetworkConfig {
    chainId: number;
    rpcUrl: string;
    tokenListType: TokenListType;
    tokenListSource: string;
    requiresApiKey: boolean;
  }

  export interface Config {
    mainnet: NetworkConfig;
    kovan: NetworkConfig;
    fuji: NetworkConfig;
    avalanche: NetworkConfig;
  }

  export const config: Config = {
    mainnet: {
      chainId: 1,
      rpcUrl: 'https://mainnet.infura.io/v3/',
      requiresApiKey: true,
      tokenListType: 'URL',
      tokenListSource:
        'https://wispy-bird-88a7.uniswap.workers.dev/?url=http://tokens.1inch.eth.link',
    },
    kovan: {
      chainId: 42,
      rpcUrl: 'https://kovan.infura.io/v3/',
      requiresApiKey: true,
      tokenListType: 'FILE',
      tokenListSource: 'src/chains/ethereum/erc20_tokens_kovan.json',
    },
    fuji: {
      chainId: 43113,
      rpcUrl: 'https://api.avax-test.network/ext/bc/C/rpc',
      requiresApiKey: false,
      tokenListType: 'FILE',
      tokenListSource: 'src/chains/avalanche/avalanche_tokens_fuji.json',
    },
    avalanche: {
      chainId: 43114,
      rpcUrl:
        //'https://speedy-nodes-nyc.moralis.io/ac8325b518a591fe9d7f1820/avalanche/mainnet',
        'https://api.avax.network/ext/bc/C/rpc',
      requiresApiKey: false,
      tokenListType: 'URL',
      tokenListSource:
        'https://raw.githubusercontent.com/pangolindex/tokenlists/main/top15.tokenlist.json',
    },
  };
}
