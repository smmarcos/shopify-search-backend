import OpenAI from 'openai';
import logger from '../utils/logger.js';
import { cacheGet, cacheSet } from '../db/redis.js';

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

const EMBEDDING_MODEL = process.env.OPENAI_MODEL || 'text-embedding-3-small';
const EMBEDDING_DIMENSION = parseInt(process.env.EMBEDDING_DIMENSION) || 1536;
const CACHE_TTL = 7 * 24 * 60 * 60; // 7 days

/**
 * Generate embedding for text
 * @param {string} text - Text to embed
 * @param {boolean} useCache - Use Redis cache
 * @returns {Promise<number[]>} - Embedding vector
 */
export async function generateEmbedding(text, useCache = true) {
  if (!text || text.trim().length === 0) {
    throw new Error('Text cannot be empty');
  }

  // Check cache
  const cacheKey = `embedding:${EMBEDDING_MODEL}:${text}`;
  if (useCache) {
    const cached = await cacheGet(cacheKey);
    if (cached) {
      logger.debug('Embedding cache hit', { text: text.substring(0, 50) });
      return cached;
    }
  }

  try {
    const response = await openai.embeddings.create({
      model: EMBEDDING_MODEL,
      input: text,
      dimensions: EMBEDDING_DIMENSION,
    });

    const embedding = response.data[0].embedding;

    // Cache result
    if (useCache) {
      await cacheSet(cacheKey, embedding, CACHE_TTL);
    }

    logger.debug('Embedding generated', {
      model: EMBEDDING_MODEL,
      textLength: text.length,
      dimension: embedding.length,
    });

    return embedding;
  } catch (error) {
    logger.error('Failed to generate embedding', {
      error: error.message,
      text: text.substring(0, 100),
    });
    throw error;
  }
}

/**
 * Generate embeddings for multiple texts (batch)
 * @param {string[]} texts - Array of texts
 * @returns {Promise<number[][]>} - Array of embedding vectors
 */
export async function generateEmbeddingsBatch(texts) {
  if (!texts || texts.length === 0) {
    return [];
  }

  // Filter empty texts
  const validTexts = texts.filter(t => t && t.trim().length > 0);
  
  if (validTexts.length === 0) {
    return [];
  }

  try {
    const response = await openai.embeddings.create({
      model: EMBEDDING_MODEL,
      input: validTexts,
      dimensions: EMBEDDING_DIMENSION,
    });

    const embeddings = response.data.map(d => d.embedding);

    logger.info('Batch embeddings generated', {
      model: EMBEDDING_MODEL,
      count: embeddings.length,
      dimension: EMBEDDING_DIMENSION,
    });

    return embeddings;
  } catch (error) {
    logger.error('Failed to generate batch embeddings', {
      error: error.message,
      count: validTexts.length,
    });
    throw error;
  }
}

/**
 * Create text representation of product for embedding
 * @param {Object} product - Product object
 * @returns {string} - Text representation
 */
export function productToText(product) {
  const parts = [];

  // Title (most important)
  if (product.title) {
    parts.push(product.title);
  }

  // Product type and vendor
  if (product.product_type) {
    parts.push(`Category: ${product.product_type}`);
  }
  
  if (product.vendor) {
    parts.push(`Brand: ${product.vendor}`);
  }

  // Description (cleaned)
  if (product.description) {
    // Remove HTML tags
    const cleanDesc = product.description.replace(/<[^>]*>/g, ' ').trim();
    parts.push(cleanDesc);
  }

  // Tags
  if (product.tags && product.tags.length > 0) {
    parts.push(`Tags: ${product.tags.join(', ')}`);
  }

  return parts.join(' | ');
}

/**
 * Generate embedding for product
 * @param {Object} product - Product object
 * @returns {Promise<number[]>} - Embedding vector
 */
export async function generateProductEmbedding(product) {
  const text = productToText(product);
  return generateEmbedding(text);
}

/**
 * Cost estimation for embeddings
 * @param {number} textCount - Number of texts
 * @param {number} avgLength - Average text length in characters
 * @returns {Object} - Cost estimation
 */
export function estimateEmbeddingCost(textCount, avgLength = 500) {
  const model = EMBEDDING_MODEL;
  
  // Token estimation (rough: 4 chars = 1 token)
  const tokensPerText = Math.ceil(avgLength / 4);
  const totalTokens = textCount * tokensPerText;

  // Pricing (per 1M tokens)
  const pricing = {
    'text-embedding-3-small': 0.02,
    'text-embedding-3-large': 0.13,
    'text-embedding-ada-002': 0.10,
  };

  const pricePerMillionTokens = pricing[model] || 0.02;
  const estimatedCost = (totalTokens / 1000000) * pricePerMillionTokens;

  return {
    model,
    textCount,
    avgLength,
    totalTokens: totalTokens.toLocaleString(),
    estimatedCost: `$${estimatedCost.toFixed(4)}`,
    pricePerMillionTokens: `$${pricePerMillionTokens}`,
  };
}

export default {
  generateEmbedding,
  generateEmbeddingsBatch,
  productToText,
  generateProductEmbedding,
  estimateEmbeddingCost,
};
