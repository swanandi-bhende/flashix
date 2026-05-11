const Redis = require('ioredis');
const { randomUUID } = require('crypto');
const DEFAULT_MAX_BUFFER = 50;

class QueueBridge {
  constructor(opts = {}) {
    this.host = process.env.REDIS_HOST || '127.0.0.1';
    this.port = process.env.REDIS_PORT ? parseInt(process.env.REDIS_PORT) : 6379;
    this.queue = opts.queue || 'flashix:queue:inference_requests';
    this.maxBuffer = opts.maxBuffer || DEFAULT_MAX_BUFFER;
    this.buffer = [];
    this.connected = false;

    this.redis = new Redis({
      host: this.host,
      port: this.port,
      retryStrategy: (times) => Math.min(times * 100, 3000),
      enableOfflineQueue: true,
      maxRetriesPerRequest: 3,
    });

    this.redis.on('connect', () => {
      this.connected = true;
      this._drainBuffer();
    });

    this.redis.on('error', (err) => this.onRedisError(err));
  }

  async _drainBuffer() {
    while (this.buffer.length > 0 && this.connected) {
      const item = this.buffer.shift();
      try {
        await this._pushToRedis(item.json, item.score);
      } catch (e) {
        console.error('Failed to drain buffered item', e);
        this.buffer.unshift(item);
        break;
      }
    }
  }

  async _pushToRedis(jsonMessage, score) {
    // zadd with member as JSON string, score numeric
    await this.redis.zadd(this.queue, { [jsonMessage]: score });
  }

  onRedisError(err) {
    console.error('Redis error in QueueBridge', err && err.message);
    this.connected = false;
  }

  async pushOpportunity(opportunity) {
    const message_id = randomUUID();
    const message = {
      message_id,
      correlation_id: opportunity.id,
      pipeline_stage: 'OPPORTUNITY_FILTERED',
      created_at_ms: Date.now(),
      hop_count: 1,
      source_component: 'mempool-listener',
      inference_input: opportunity, // lightweight carry-through
    };

    const jsonMessage = JSON.stringify(message);
    const score = -1 * (opportunity.opportunityScore || 0);

    try {
      if (!this.connected) throw new Error('redis-not-connected');
      await this._pushToRedis(jsonMessage, score);
      await this.redis.hset(`flashix:correlation:${opportunity.id}`, {
        current_stage: 'OPPORTUNITY_FILTERED',
        inference_requested_at: Date.now(),
        created_at: Date.now(),
      });
      const qDepth = await this.redis.zcard(this.queue);
      console.info(`QUEUED: correlation_id=${opportunity.id}, score=${opportunity.opportunityScore}, queue_depth=${qDepth}`);
    } catch (err) {
      console.warn('Redis unavailable; buffering opportunity', err && err.message);
      if (this.buffer.length < this.maxBuffer) {
        this.buffer.push({ json: jsonMessage, score });
      } else {
        console.error('Buffer full, dropping opportunity', opportunity.id);
      }
    }
  }
}

module.exports = { QueueBridge };
