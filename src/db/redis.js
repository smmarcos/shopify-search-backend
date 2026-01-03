import Redis from 'ioredis';
import dotenv from 'dotenv';
import logger from '../utils/logger.js';

dotenv.config();

const redis = new Redis(process.env.REDIS_URL, {
  maxRetriesPerRequest: 3,
  retryStrategy(times) {
    const delay = Math.min(times * 50, 2000);
    return delay;
  },
});

redis.on('connect', () => {
  logger.info('✅ Redis connected');
});

redis.on('error', (error) => {
  logger.error('❌ Redis error', { error: error.message });
});

export async function connectRedis() {
  try {
    await redis.ping();
    logger.info('✅ Redis ping successful');
  } catch (error) {
    logger.error('❌ Redis connection failed', { error: error.message });
    throw error;
  }
}

// Cache helpers
export async function cacheGet(key) {
  try {
    const value = await redis.get(key);
    return value ? JSON.parse(value) : null;
  } catch (error) {
    logger.error('Cache get failed', { key, error: error.message });
    return null;
  }
}

export async function cacheSet(key, value, ttlSeconds = 3600) {
  try {
    await redis.setex(key, ttlSeconds, JSON.stringify(value));
  } catch (error) {
    logger.error('Cache set failed', { key, error: error.message });
  }
}

export async function cacheDel(key) {
  try {
    await redis.del(key);
  } catch (error) {
    logger.error('Cache delete failed', { key, error: error.message });
  }
}

export default redis;
