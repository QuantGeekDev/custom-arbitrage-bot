export namespace UniswapConfig {
  export interface NetworkConfig {
    uniswapV2RouterAddress: string;
    uniswapV3RouterAddress: string;
    uniswapV3NftManagerAddress: string;
  }
  export interface AvalancheNetworkConfig {
    routerAddress: string;
  }

  export interface Config {
    mainnet: NetworkConfig;
    kovan: NetworkConfig;
    fuji: AvalancheNetworkConfig;
    avalanche: AvalancheNetworkConfig;
  }

  // contract addresses on mainnet and kovan are the same for Uniswap
  export const config: Config = {
    mainnet: {
      uniswapV2RouterAddress: '0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D',
      uniswapV3RouterAddress: '0xE592427A0AEce92De3Edee1F18E0157C05861564',
      uniswapV3NftManagerAddress: '0xC36442b4a4522E871399CD717aBDD847Ab11FE88',
    },
    kovan: {
      uniswapV2RouterAddress: '0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D',
      uniswapV3RouterAddress: '0xE592427A0AEce92De3Edee1F18E0157C05861564',
      uniswapV3NftManagerAddress: '0xC36442b4a4522E871399CD717aBDD847Ab11FE88',
    },
    fuji: {
      routerAddress: '0xE54Ca86531e17Ef3616d22Ca28b0D458b6C89106',
    },
    avalanche: {
      routerAddress: '0xE54Ca86531e17Ef3616d22Ca28b0D458b6C89106',
    },
  };
}
