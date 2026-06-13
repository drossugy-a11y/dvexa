/**
 * CopilotKit 后端代理
 * 连接小米 MiMo API，提供流式 AI 聊天服务
 */

import express from 'express';
import cors from 'cors';
import { CopilotRuntime, OpenAIAdapter, copilotRuntimeNodeServerEndpoint } from '@copilotkit/runtime';
import OpenAI from 'openai';
import dotenv from 'dotenv';

dotenv.config();

const app = express();
app.use(cors());
app.use(express.json());

// MiMo API 配置
const openai = new OpenAI({
  apiKey: process.env.MIMO_API_KEY || '',
  baseURL: process.env.MIMO_BASE_URL || 'https://api.xiaomimimo.com/v1',
});

const serviceAdapter = new OpenAIAdapter({
  openai,
  model: process.env.MIMO_MODEL || 'MiMo-V2.5-Pro',
});

const runtime = new CopilotRuntime({
  serviceAdapter,
});

// CopilotKit 端点
const copilotHandler = copilotRuntimeNodeServerEndpoint({
  runtime,
  endpoint: '/api/copilotkit',
});

app.use('/api/copilotkit', copilotHandler);

// 健康检查
app.get('/api/copilotkit/health', (req, res) => {
  res.json({
    status: 'ok',
    model: process.env.MIMO_MODEL,
    base_url: process.env.MIMO_BASE_URL,
  });
});

const PORT = process.env.COPILOTKIT_PORT || 3001;
app.listen(PORT, () => {
  console.log(`CopilotKit runtime running on http://localhost:${PORT}`);
  console.log(`Model: ${process.env.MIMO_MODEL}`);
});
