import { query } from '../db/database.js';
import logger from '../utils/logger.js';
import { generateEmbedding } from './embedding.js';

const SIMILARITY_THRESHOLD = parseFloat(process.env.SIMILARITY_THRESHOLD) || 0.7;
const SEARCH_TOP_K = parseInt(process.env.SEARCH_TOP_K) || 20;

/**
 * Semantic search for products
 * @param {number} storeId - Store ID
 * @param {string} searchQuery - User query
 * @param {Object} options - Search options
 * @returns {Promise<Array>} - Search results
 */
export async function semanticSearch(storeId, searchQuery, options = {}) {
  const startTime = Date.now();

  try {
    // Generate embedding for query
    const queryEmbedding = await generateEmbedding(searchQuery);

    // Build filters
    const filters = buildFilters(options);

    // Execute vector search
    const sqlQuery = `
      SELECT 
        p.id,
        p.shopify_product_id,
        p.title,
        p.description,
        p.handle,
        p.vendor,
        p.product_type,
        p.tags,
        p.price_min,
        p.price_max,
        p.image_url,
        p.available,
        (1 - (p.embedding <=> $2::vector))::DECIMAL(5, 4) as similarity
      FROM products p
      WHERE 
        p.store_id = $1
        AND p.available = true
        ${filters.sql}
        AND (1 - (p.embedding <=> $2::vector)) >= $3
      ORDER BY p.embedding <=> $2::vector
      LIMIT $4
    `;

    const params = [
      storeId,
      `[${queryEmbedding.join(',')}]`,
      options.similarityThreshold || SIMILARITY_THRESHOLD,
      options.limit || SEARCH_TOP_K,
      ...filters.params,
    ];

    const result = await query(sqlQuery, params);

    // Apply re-ranking if needed
    let results = result.rows;
    if (options.rerank) {
      results = rerankResults(results, options.rerank);
    }

    const duration = Date.now() - startTime;

    logger.info('Semantic search completed', {
      storeId,
      query: searchQuery,
      resultsCount: results.length,
      duration: `${duration}ms`,
    });

    return {
      query: searchQuery,
      results,
      count: results.length,
      duration,
      timestamp: new Date().toISOString(),
    };
  } catch (error) {
    logger.error('Semantic search failed', {
      storeId,
      query: searchQuery,
      error: error.message,
    });
    throw error;
  }
}

/**
 * Build SQL filters from options
 * @param {Object} options - Filter options
 * @returns {Object} - SQL string and params
 */
function buildFilters(options) {
  const conditions = [];
  const params = [];
  let paramIndex = 5; // Start after main query params

  if (options.priceMin !== undefined) {
    conditions.push(`p.price_min >= $${paramIndex}`);
    params.push(options.priceMin);
    paramIndex++;
  }

  if (options.priceMax !== undefined) {
    conditions.push(`p.price_max <= $${paramIndex}`);
    params.push(options.priceMax);
    paramIndex++;
  }

  if (options.vendor) {
    conditions.push(`p.vendor ILIKE $${paramIndex}`);
    params.push(`%${options.vendor}%`);
    paramIndex++;
  }

  if (options.productType) {
    conditions.push(`p.product_type ILIKE $${paramIndex}`);
    params.push(`%${options.productType}%`);
    paramIndex++;
  }

  if (options.tags && options.tags.length > 0) {
    conditions.push(`p.tags && $${paramIndex}`);
    params.push(options.tags);
    paramIndex++;
  }

  if (options.inStock) {
    conditions.push(`p.inventory_quantity > 0`);
  }

  const sql = conditions.length > 0 
    ? `AND ${conditions.join(' AND ')}`
    : '';

  return { sql, params };
}

/**
 * Re-rank results based on business rules
 * @param {Array} results - Search results
 * @param {Object} rankingRules - Ranking configuration
 * @returns {Array} - Re-ranked results
 */
function rerankResults(results, rankingRules) {
  return results.map(product => {
    let score = parseFloat(product.similarity);

    // Boost by availability
    if (product.available && product.inventory_quantity > 0) {
      score *= rankingRules.inStockBoost || 1.1;
    }

    // Boost by price range (e.g., products in sweet spot)
    if (rankingRules.preferredPriceRange) {
      const { min, max } = rankingRules.preferredPriceRange;
      if (product.price_min >= min && product.price_max <= max) {
        score *= rankingRules.priceRangeBoost || 1.05;
      }
    }

    // Boost by popularity (if available)
    if (product.popularity_score) {
      score *= (1 + (product.popularity_score / 100));
    }

    return { ...product, final_score: score };
  }).sort((a, b) => b.final_score - a.final_score);
}

/**
 * Find similar products to a given product
 * @param {number} storeId - Store ID
 * @param {number} productId - Product ID
 * @param {number} limit - Number of results
 * @returns {Promise<Array>} - Similar products
 */
export async function findSimilarProducts(storeId, productId, limit = 10) {
  try {
    const sqlQuery = `
      SELECT 
        p2.id,
        p2.title,
        p2.description,
        p2.price_min,
        p2.image_url,
        (1 - (p1.embedding <=> p2.embedding))::DECIMAL(5, 4) as similarity
      FROM products p1
      CROSS JOIN products p2
      WHERE 
        p1.id = $1
        AND p2.store_id = $2
        AND p2.id != $1
        AND p2.available = true
      ORDER BY p1.embedding <=> p2.embedding
      LIMIT $3
    `;

    const result = await query(sqlQuery, [productId, storeId, limit]);

    logger.info('Similar products found', {
      storeId,
      productId,
      count: result.rows.length,
    });

    return result.rows;
  } catch (error) {
    logger.error('Find similar products failed', {
      storeId,
      productId,
      error: error.message,
    });
    throw error;
  }
}

/**
 * Get search suggestions based on partial query
 * @param {number} storeId - Store ID
 * @param {string} partialQuery - Partial search query
 * @param {number} limit - Number of suggestions
 * @returns {Promise<Array>} - Suggestions
 */
export async function getSearchSuggestions(storeId, partialQuery, limit = 5) {
  try {
    // Simple approach: match against product titles
    const sqlQuery = `
      SELECT DISTINCT
        title,
        COUNT(*) as frequency
      FROM products
      WHERE 
        store_id = $1
        AND available = true
        AND title ILIKE $2
      GROUP BY title
      ORDER BY frequency DESC, title
      LIMIT $3
    `;

    const result = await query(sqlQuery, [
      storeId,
      `%${partialQuery}%`,
      limit,
    ]);

    return result.rows.map(row => row.title);
  } catch (error) {
    logger.error('Get search suggestions failed', {
      storeId,
      partialQuery,
      error: error.message,
    });
    return [];
  }
}

export default {
  semanticSearch,
  findSimilarProducts,
  getSearchSuggestions,
};
