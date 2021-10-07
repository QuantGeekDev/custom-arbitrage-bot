/* eslint-disable @typescript-eslint/ban-types */
import { Wallet } from 'ethers';
import { NextFunction, Router, Request, Response } from 'express';
import { AvalancheConfig } from './avalanche.config';
import { ConfigManager } from '../../services/config-manager';
import { HttpException, asyncHandler } from '../../services/error-handler';
import { latency } from '../../services/base';
import { tokenValueToString } from '../../services/base';
import { Avalanche } from './avalanche';
import {
  EthereumAllowancesRequest,
  EthereumAllowancesResponse,
  EthereumApproveRequest,
  EthereumApproveResponse,
  EthereumBalanceRequest,
  EthereumBalanceResponse,
  EthereumNonceRequest,
  EthereumNonceResponse,
  EthereumPollRequest,
  EthereumPollResponse,
} from '../ethereum/ethereum.routes';
import {
  approve,
  poll,
  getTokenSymbolsToTokens,
} from '../ethereum/ethereum.controllers';
import { PangolinConfig } from './pangolin/pangolin.config';

function getSpender(reqSpender: string): string {
  let spender: string;
  if (reqSpender === 'pangolin') {
    if (ConfigManager.config.ETHEREUM_CHAIN === 'avalanche') {
      spender = PangolinConfig.config.avalanche.routerAddress;
    } else {
      spender = PangolinConfig.config.fuji.routerAddress;
    }
  } else {
    spender = reqSpender;
  }

  return spender;
}

export namespace AvalancheRoutes {
  export const router = Router();
  export const avalanche = Avalanche.getInstance();
  export const reload = (): void => {
    // avalanche = Avalanche.reload();
  };

  router.use(
    asyncHandler(async (_req: Request, _res: Response, next: NextFunction) => {
      if (!avalanche.ready()) {
        await avalanche.init();
      }
      return next();
    })
  );

  router.get(
    '/',
    asyncHandler(async (_req: Request, res: Response) => {
      let rpcUrl;
      if (ConfigManager.config.AVALANCHE_CHAIN === 'avalanche') {
        rpcUrl = AvalancheConfig.config.avalanche.rpcUrl;
      } else {
        rpcUrl = AvalancheConfig.config.fuji.rpcUrl;
      }

      res.status(200).json({
        network: ConfigManager.config.AVALANCHE_CHAIN,
        rpcUrl: rpcUrl,
        connection: true,
        timestamp: Date.now(),
      });
    })
  );

  router.post(
    '/nonce',
    asyncHandler(
      async (
        req: Request<{}, {}, EthereumNonceRequest>,
        res: Response<EthereumNonceResponse | string, {}>
      ) => {
        // get the address via the private key since we generally use the private
        // key to interact with gateway and the address is not part of the user config
        const wallet = avalanche.getWallet(req.body.privateKey);
        const nonce = await avalanche.nonceManager.getNonce(wallet.address);
        res.status(200).json({ nonce: nonce });
      }
    )
  );

  router.post(
    '/allowances',
    asyncHandler(
      async (
        req: Request<{}, {}, EthereumAllowancesRequest>,
        res: Response<EthereumAllowancesResponse | string, {}>
      ) => {
        const initTime = Date.now();
        const wallet = avalanche.getWallet(req.body.privateKey);
        const tokens = getTokenSymbolsToTokens(
          avalanche,
          req.body.tokenSymbols
        );
        const spender = getSpender(req.body.spender);

        const approvals: Record<string, string> = {};
        await Promise.all(
          Object.keys(tokens).map(async (symbol) => {
            approvals[symbol] = tokenValueToString(
              await avalanche.getERC20Allowance(
                wallet,
                spender,
                tokens[symbol].address,
                tokens[symbol].decimals
              )
            );
          })
        );

        res.status(200).json({
          network: ConfigManager.config.AVALANCHE_CHAIN,
          timestamp: initTime,
          latency: latency(initTime, Date.now()),
          spender: spender,
          approvals: approvals,
        });
      }
    )
  );

  router.post(
    '/balances',
    asyncHandler(
      async (
        req: Request<{}, {}, EthereumBalanceRequest>,
        res: Response<EthereumBalanceResponse | string, {}>,
        _next: NextFunction
      ) => {
        const initTime = Date.now();

        let wallet: Wallet;
        try {
          wallet = avalanche.getWallet(req.body.privateKey);
        } catch (err) {
          throw new HttpException(500, 'Error getting wallet ' + err);
        }

        const tokens = getTokenSymbolsToTokens(
          avalanche,
          req.body.tokenSymbols
        );

        const balances: Record<string, string> = {};
        balances.AVAX = tokenValueToString(
          await avalanche.getEthBalance(wallet)
        );

        await Promise.all(
          Object.keys(tokens).map(async (symbol) => {
            if (tokens[symbol] !== undefined) {
              const address = tokens[symbol].address;
              const decimals = tokens[symbol].decimals;
              const balance = await avalanche.getERC20Balance(
                wallet,
                address,
                decimals
              );
              balances[symbol] = tokenValueToString(balance);
            }
          })
        );

        res.status(200).json({
          network: ConfigManager.config.AVALANCHE_CHAIN,
          timestamp: initTime,
          latency: latency(initTime, Date.now()),
          balances: balances,
        });
      }
    )
  );

  router.post(
    '/approve',
    asyncHandler(
      async (
        req: Request<{}, {}, EthereumApproveRequest>,
        res: Response<EthereumApproveResponse | string, {}>
      ) => {
        const { nonce, privateKey, token, amount } = req.body;
        const spender = getSpender(req.body.spender);
        const result = await approve(
          avalanche,
          spender,
          privateKey,
          token,
          amount,
          nonce
        );
        return res.status(200).json({
          network: ConfigManager.config.ETHEREUM_CHAIN,
          ...result,
        });
      }
    )
  );

  router.post(
    '/poll',
    asyncHandler(
      async (
        req: Request<{}, {}, EthereumPollRequest>,
        res: Response<EthereumPollResponse, {}>
      ) => {
        const result = await poll(avalanche, req.body.txHash);
        return res.status(200).json({
          network: ConfigManager.config.ETHEREUM_CHAIN,
          ...result,
        });
      }
    )
  );
}
