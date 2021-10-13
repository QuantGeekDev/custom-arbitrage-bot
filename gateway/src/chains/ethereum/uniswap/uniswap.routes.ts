import { Router, Request, Response, NextFunction } from 'express';
import { Ethereum } from '../ethereum';
import { Uniswap } from './uniswap';
import { ConfigManager } from '../../../services/config-manager';
import { HttpException, asyncHandler } from '../../../services/error-handler';
import { BigNumber, Wallet } from 'ethers';
import { latency, gasCostInEthString } from '../../../services/base';
import { Trade } from '@uniswap/sdk';
import { getAmountInBigNumber, getTrade } from './uniswap.controllers';

type Side = 'BUY' | 'SELL';
export interface UniswapPriceRequest {
  quote: string;
  base: string;
  amount: string;
  side: Side;
}

export interface UniswapPriceResponse {
  network: string;
  timestamp: number;
  latency: number;
  base: string;
  quote: string;
  amount: string;
  expectedAmount: string;
  price: string;
  gasPrice: number;
  gasLimit: number;
  gasCost: string;
  trade: Trade;
}

export interface UniswapTradeRequest {
  quote: string;
  base: string;
  amount: string;
  privateKey: string;
  side: Side;
  limitPrice?: BigNumber;
  nonce?: number;
}

export interface UniswapTradeResponse {
  network: string;
  timestamp: number;
  latency: number;
  base: string;
  quote: string;
  amount: string;
  expectedIn?: string;
  expectedOut?: string;
  price: string;
  gasPrice: number;
  gasLimit: number;
  gasCost: string;
  nonce: number;
  txHash: string | undefined;
}

export interface UniswapTradeErrorResponse {
  error: string;
  message: string;
}
export namespace UniswapRoutes {
  export const router = Router();
  export const uniswap = Uniswap.getInstance();
  export const ethereum = Ethereum.getInstance();

  router.use(
    asyncHandler(async (_req: Request, _res: Response, next: NextFunction) => {
      if (!ethereum.ready()) {
        await ethereum.init();
      }
      if (!uniswap.ready()) {
        await uniswap.init();
      }
      return next();
    })
  );

  router.get('/', async (_req: Request, res: Response) => {
    res.status(200).json({
      network: ConfigManager.config.ETHEREUM_CHAIN,
      uniswap_router: uniswap.uniswapRouter,
      connection: true,
      timestamp: Date.now(),
    });
  });

  router.post(
    '/price',
    asyncHandler(
      async (
        req: Request<{}, {}, UniswapPriceRequest>,
        res: Response<UniswapPriceResponse, {}>
      ) => {
        const initTime = Date.now();
        let amount: BigNumber;
        try {
          amount = getAmountInBigNumber(
            ethereum,
            req.body.amount,
            req.body.side,
            req.body.quote,
            req.body.base
          );
        } catch (error: any) {
          throw new HttpException(500, error.message);
        }

        const baseToken = ethereum.getTokenBySymbol(req.body.base);
        const quoteToken = ethereum.getTokenBySymbol(req.body.quote);

        if (!baseToken || !quoteToken)
          throw new HttpException(
            500,
            'Unrecognized base token symbol: ' + baseToken
              ? req.body.quote
              : req.body.base
          );
        let trade;
        try {
          trade = await getTrade(
            uniswap,
            req.body.side,
            quoteToken.address,
            baseToken.address,
            amount
          );
        } catch (error: any) {
          throw new HttpException(500, error.message);
        }

        res.status(200).json({
          network: ConfigManager.config.ETHEREUM_CHAIN,
          timestamp: initTime,
          latency: latency(initTime, Date.now()),
          base: baseToken.address,
          quote: quoteToken.address,
          amount: amount.toString(),
          expectedAmount: trade.expectedAmount.toSignificant(8),
          price: trade.tradePrice.toSignificant(8),
          gasPrice: ethereum.gasPrice,
          gasLimit: ConfigManager.config.UNISWAP_GAS_LIMIT,
          gasCost: gasCostInEthString(
            ethereum.gasPrice,
            ConfigManager.config.UNISWAP_GAS_LIMIT
          ),
          trade: trade.trade,
        });
      }
    )
  );

  router.post(
    '/trade',
    asyncHandler(
      async (
        req: Request<{}, {}, UniswapTradeRequest>,
        res: Response<UniswapTradeResponse | UniswapTradeErrorResponse, {}>
      ) => {
        const initTime = Date.now();
        const limitPrice = req.body.limitPrice;

        let wallet: Wallet;
        try {
          wallet = ethereum.getWallet(req.body.privateKey);
        } catch (err) {
          throw new Error(`Error getting wallet ${err}`);
        }

        const baseToken = ethereum.getTokenBySymbol(req.body.base);
        const quoteToken = ethereum.getTokenBySymbol(req.body.quote);
        if (!baseToken || !quoteToken)
          throw new HttpException(
            500,
            'Unrecognized base token symbol: ' + baseToken
              ? req.body.quote
              : req.body.base
          );

        let amount: BigNumber;
        try {
          amount = getAmountInBigNumber(
            ethereum,
            req.body.amount,
            req.body.side,
            req.body.quote,
            req.body.base
          );
        } catch (error: any) {
          throw new HttpException(500, error.message);
        }

        let trade;
        try {
          trade = await getTrade(
            uniswap,
            req.body.side,
            quoteToken.address,
            baseToken.address,
            amount
          );
        } catch (error: any) {
          throw new HttpException(500, error.message);
        }

        const gasPrice = ethereum.gasPrice;
        const gasLimit = ConfigManager.config.UNISWAP_GAS_LIMIT;

        if (limitPrice && trade.tradePrice.toFixed(8) >= limitPrice.toString())
          throw new HttpException(
            500,
            req.body.side === 'BUY'
              ? `Swap price ${trade.tradePrice} exceeds limitPrice ${limitPrice}`
              : `Swap price ${trade.tradePrice} lower than limitPrice ${limitPrice}`
          );

        const tx = await uniswap.executeTrade(
          wallet,
          trade.trade,
          gasPrice,
          req.body.nonce
        );

        const response: UniswapTradeResponse = {
          network: ConfigManager.config.ETHEREUM_CHAIN,
          timestamp: initTime,
          latency: latency(initTime, Date.now()),
          base: baseToken.address,
          quote: quoteToken.address,
          amount: amount.toString(),
          price: trade.tradePrice.toSignificant(8),
          gasPrice: gasPrice,
          gasLimit: gasLimit,
          gasCost: gasCostInEthString(gasPrice, gasLimit),
          nonce: tx.nonce,
          txHash: tx.hash,
        };
        const expectedKey =
          req.body.side === 'BUY' ? 'expectedIn' : 'expectedOut';

        response[expectedKey] = trade.expectedAmount.toSignificant(8);
        return res.status(200).json(response);
      }
    )
  );
}
