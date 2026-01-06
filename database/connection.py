"""
Database connection and utilities for pgvector
"""

import os
import json
from typing import List, Dict, Optional
import asyncpg
from asyncpg.pool import Pool


class DatabaseClient:
    def __init__(self):
        self.pool: Optional[Pool] = None
        self.connection_string = os.environ.get(
            "DATABASE_URL",
            "postgresql://postgres:postgres@localhost:5432/shopify_search"
        )
    
    async def connect(self):
        """Create connection pool"""
        if self.pool is None:
            self.pool = await asyncpg.create_pool(
                self.connection_string,
                min_size=5,
                max_size=20,
                command_timeout=60
            )
        return self.pool
    
    async def disconnect(self):
        """Close connection pool"""
        if self.pool:
            await self.pool.close()
            self.pool = None
    
    async def vector_search(
        self, 
        query_embedding: List[float], 
        limit: int = 10,
        max_price: Optional[float] = None,
        min_price: Optional[float] = None,
        in_stock_only: bool = False,
        shop: Optional[str] = None
    ) -> List[Dict]:
        """
        Perform vector similarity search
        
        Args:
            query_embedding: Vector embedding of search query
            limit: Maximum results
            max_price: Filter by maximum price
            min_price: Filter by minimum price
            in_stock_only: Only return in-stock products
            shop: Filter by shop domain
        
        Returns:
            List of products with similarity scores
        """
        print(f"🔍 vector_search called - query_embedding type: {type(query_embedding)}, len: {len(query_embedding) if isinstance(query_embedding, list) else 'N/A'}")
        pool = await self.connect()
        
        # Convert embedding list to string format for pgvector (without brackets for direct cast)
        # PostgreSQL vector type expects: [1.0,2.0,3.0] format
        embedding_str = f"[{','.join(map(str, query_embedding))}]"
        print(f"✅ embedding_str created: {embedding_str[:80]}...")
        
        # Build WHERE clause dynamically
        where_conditions = []
        params = []
        param_counter = 1  # Start from $1 for first filter param
        
        # NOTE: embedding is NOT a param - it's embedded in query to avoid type issues
        
        if max_price is not None:
            where_conditions.append(f"price <= ${param_counter}")
            params.append(max_price)
            param_counter += 1
        
        if min_price is not None:
            where_conditions.append(f"price >= ${param_counter}")
            params.append(min_price)
            param_counter += 1
        
        if in_stock_only:
            where_conditions.append("(metadata->>'in_stock')::boolean = true")
        
        if shop:
            where_conditions.append(f"shop_domain = ${param_counter}")
            params.append(shop)
            param_counter += 1
        
        # Always ensure embedding is not NULL
        where_conditions.append("embedding IS NOT NULL")
        
        # Build complete WHERE clause
        where_clause = " AND ".join(where_conditions)
        
        # Build query with embedding cast properly (NO quotes around embedding_str)
        # pgvector needs: [1,2,3]::vector NOT '[1,2,3]'::vector
        query = f"""
            SELECT 
                product_id,
                title,
                description,
                price,
                vendor,
                category,
                tags,
                metadata,
                1 - (embedding <=> {embedding_str}::vector) as similarity_score
            FROM product_embeddings
            WHERE {where_clause}
            ORDER BY embedding <=> {embedding_str}::vector
            LIMIT {limit}
        """
        
        print(f"📝 Query params count: {len(params)}, types: {[type(p).__name__ for p in params]}")
        print(f"🔍 WHERE clause: {where_clause}")
        print(f"📄 Embedding cast: {embedding_str[:60]}::vector")
        
        async with pool.acquire() as conn:
            try:
                rows = await conn.fetch(query, *params)
                print(f"✅ Query executed successfully, returned {len(rows)} rows")
            except Exception as e:
                print(f"❌ Query execution failed: {str(e)}")
                print(f"❌ Query was: {query[:500]}")
                raise
        
        # Parse metadata JSON strings back to dicts
        import json
        results = []
        for row in rows:
            row_dict = dict(row)
            if isinstance(row_dict.get('metadata'), str):
                row_dict['metadata'] = json.loads(row_dict['metadata'])
            results.append(row_dict)
        
        print(f"📦 Returning {len(results)} results")
        return results
    
    async def get_product_by_id(self, product_id: str) -> Optional[Dict]:
        """Get product details by ID"""
        pool = await self.connect()
        
        query = """
            SELECT 
                product_id,
                title,
                description,
                price,
                vendor,
                category,
                tags,
                metadata
            FROM product_embeddings
            WHERE product_id = $1
        """
        
        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, product_id)
        
        if not row:
            return None
        
        # Parse metadata JSON string back to dict
        import json
        row_dict = dict(row)
        if isinstance(row_dict.get('metadata'), str):
            row_dict['metadata'] = json.loads(row_dict['metadata'])
        
        return row_dict
    
    async def upsert_product(
        self,
        product_id: str,
        title: str,
        shop_domain: str,
        embedding: Optional[List[float]] = None,
        description: Optional[str] = None,
        price: Optional[float] = None,
        vendor: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict] = None
    ) -> bool:
        """Insert or update product with embedding"""
        pool = await self.connect()
        
        query = """
            INSERT INTO product_embeddings 
                (product_id, shop_domain, title, description, price, vendor, category, tags, embedding, metadata)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::vector, $10::jsonb)
            ON CONFLICT (product_id, shop_domain) 
            DO UPDATE SET
                title = EXCLUDED.title,
                description = EXCLUDED.description,
                price = EXCLUDED.price,
                vendor = EXCLUDED.vendor,
                category = EXCLUDED.category,
                tags = EXCLUDED.tags,
                embedding = EXCLUDED.embedding,
                metadata = EXCLUDED.metadata,
                updated_at = CURRENT_TIMESTAMP
            RETURNING id
        """
        
        # Convert embedding list to string format for pgvector (or NULL if None)
        embedding_str = f"[{','.join(map(str, embedding))}]" if embedding else None
        
        # Convert metadata dict to JSON string
        import json
        metadata_str = json.dumps(metadata or {})
        
        async with pool.acquire() as conn:
            result = await conn.fetchval(
                query,
                product_id,
                shop_domain,
                title,
                description,
                price,
                vendor,
                category,
                tags or [],
                embedding_str,
                metadata_str
            )
        
        return result is not None
    
    async def upsert_product_info(
        self,
        product_id: str,
        shop_domain: str,
        title: str,
        description: str,
        price: float,
        vendor: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict] = None
    ) -> bool:
        """
        Insert or update product WITHOUT touching embedding field.
        This preserves existing embeddings when refreshing from Shopify.
        """
        pool = await self.connect()
        
        # Convert metadata dict to JSON string
        import json
        metadata_str = json.dumps(metadata or {})
        
        # Check if product exists for this shop
        check_query = "SELECT embedding FROM product_embeddings WHERE product_id = $1 AND shop_domain = $2"
        
        async with pool.acquire() as conn:
            existing = await conn.fetchrow(check_query, product_id, shop_domain)
            
            if existing:
                # Product exists - UPDATE without touching embedding
                update_query = """
                    UPDATE product_embeddings 
                    SET title = $3,
                        description = $4,
                        price = $5,
                        vendor = $6,
                        category = $7,
                        tags = $8,
                        metadata = $9::jsonb,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE product_id = $1 AND shop_domain = $2
                    RETURNING id
                """
                result = await conn.fetchval(
                    update_query,
                    product_id, shop_domain, title, description, price,
                    vendor, category, tags or [], metadata_str
                )
            else:
                # New product - INSERT without embedding (NULL)
                insert_query = """
                    INSERT INTO product_embeddings 
                        (product_id, shop_domain, title, description, price, vendor, category, tags, metadata)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb)
                    RETURNING id
                """
                result = await conn.fetchval(
                    insert_query,
                    product_id, shop_domain, title, description, price,
                    vendor, category, tags or [], metadata_str
                )
        
        return result is not None
    
    async def track_search(
        self,
        query: str,
        results_count: int,
        session_id: Optional[str] = None
    ):
        """Track search analytics"""
        pool = await self.connect()
        
        query_sql = """
            INSERT INTO search_analytics (query, results_count, session_id)
            VALUES ($1, $2, $3)
        """
        
        async with pool.acquire() as conn:
            await conn.execute(query_sql, query, results_count, session_id)
    
    async def get_search_stats(self, days: int = 7, shop_domain: str = None) -> Dict:
        """Get comprehensive search analytics for last N days filtered by shop"""
        pool = await self.connect()
        
        # Build WHERE clause
        where_clause = f"WHERE created_at >= NOW() - INTERVAL '{days} days'"
        if shop_domain:
            where_clause += f" AND shop_domain = '{shop_domain}'"
        
        async with pool.acquire() as conn:
            # 1. DAILY STATS - Searches by day  
            daily_query = f"""
                SELECT 
                    DATE(created_at) as date,
                    COUNT(*) as total_searches,
                    COUNT(*) FILTER (WHERE results_count > 0) as searches_with_results,
                    COUNT(*) FILTER (WHERE results_count = 0) as searches_no_results,
                    ROUND(AVG(COALESCE(results_count, 0)), 2) as avg_results
                FROM search_analytics
                {where_clause}
                GROUP BY DATE(created_at)
                ORDER BY date DESC
            """
            daily_stats = await conn.fetch(daily_query)
            
            # 2. TOP SEARCHES - Most frequent queries
            top_query = f"""
                SELECT 
                    query,
                    COUNT(*) as search_count,
                    ROUND(AVG(COALESCE(results_count, 0)), 2) as avg_results,
                    MAX(created_at) as last_searched
                FROM search_analytics
                {where_clause}
                GROUP BY query
                ORDER BY search_count DESC
                LIMIT 20
            """
            top_searches = await conn.fetch(top_query)
            
            # 3. RECENT SEARCHES - Last 50 searches
            recent_query = f"""
                SELECT 
                    id,
                    query,
                    COALESCE(results_count, 0) as results_count,
                    created_at
                FROM search_analytics
                {where_clause}
                ORDER BY created_at DESC
                LIMIT 50
            """
            recent_searches = await conn.fetch(recent_query)
            
            # 4. SUMMARY STATS
            summary_query = f"""
                SELECT 
                    COUNT(*) as total_searches,
                    COUNT(DISTINCT query) as unique_queries,
                    COUNT(*) FILTER (WHERE COALESCE(results_count, 0) = 0) as no_results_count,
                    ROUND(AVG(COALESCE(results_count, 0)), 2) as avg_results
                FROM search_analytics
                {where_clause}
            """
            summary = await conn.fetchrow(summary_query)
        
        return {
            "period_days": days,
            "daily_stats": [
                {
                    "date": str(row['date']),
                    "total_searches": row['total_searches'],
                    "searches_with_results": row['searches_with_results'],
                    "searches_no_results": row['searches_no_results'],
                    "avg_results": float(row['avg_results']) if row['avg_results'] else 0
                }
                for row in daily_stats
            ],
            "top_searches": [
                {
                    "query": row['query'],
                    "count": row['search_count'],
                    "avg_results": float(row['avg_results']) if row['avg_results'] else 0,
                    "last_searched": row['last_searched'].isoformat()
                }
                for row in top_searches
            ],
            "recent_searches": [
                {
                    "id": row['id'],
                    "query": row['query'],
                    "results_count": row['results_count'],
                    "created_at": row['created_at'].isoformat()
                }
                for row in recent_searches
            ],
            "summary": {
                "total_searches": summary['total_searches'],
                "unique_queries": summary['unique_queries'],
                "no_results_count": summary['no_results_count'],
                "avg_results": float(summary['avg_results']) if summary['avg_results'] else 0,
                "no_results_percentage": round((summary['no_results_count'] / summary['total_searches'] * 100) if summary['total_searches'] > 0 else 0, 1)
            }
        }

    async def update_product_embedding(self, product_id: str, embedding: List[float]):
        """Update a product's embedding in the database and clear needs_resync flag"""
        pool = await self.connect()
        
        # Convert embedding list to string format for pgvector
        embedding_str = f"[{','.join(map(str, embedding))}]"
        
        print(f"🔧 Updating embedding for {product_id}")
        print(f"🔧 Embedding length: {len(embedding)}")
        print(f"🔧 Embedding str preview: {embedding_str[:100]}...")
        
        query = """
            UPDATE product_embeddings 
            SET embedding = $2::vector, 
                metadata = jsonb_set(COALESCE(metadata, '{}'::jsonb), '{needs_resync}', 'false'::jsonb),
                updated_at = CURRENT_TIMESTAMP
            WHERE product_id = $1
        """
        
        async with pool.acquire() as conn:
            result = await conn.execute(query, product_id, embedding_str)
            
        # Check if any row was updated
        rows_updated = int(result.split()[-1])
        if rows_updated == 0:
            raise Exception(f"Product {product_id} not found or not updated")
            
        print(f"✅ Updated embedding for product {product_id} ({rows_updated} rows)")
        return True
    
    async def get_all_product_ids(self) -> List[str]:
        """Get all product IDs from the database"""
        pool = await self.connect()
        
        query = "SELECT product_id FROM product_embeddings LIMIT 10"
        
        async with pool.acquire() as conn:
            rows = await conn.fetch(query)
            
        return [row['product_id'] for row in rows]
    
    async def get_all_products_with_status(self, shop_domain: str = None) -> List[Dict]:
        """Get all products with their sync status, optionally filtered by shop"""
        pool = await self.connect()
        
        where_clause = f"WHERE shop_domain = '{shop_domain}'" if shop_domain else ""
        
        query = f"""
            SELECT 
                product_id,
                title,
                description,
                price,
                vendor,
                metadata,
                CASE 
                    WHEN embedding IS NOT NULL THEN true
                    ELSE false
                END as has_embedding,
                updated_at
            FROM product_embeddings
            {where_clause}
            ORDER BY updated_at DESC
        """
        
        async with pool.acquire() as conn:
            rows = await conn.fetch(query)
            
        return [
            {
                "product_id": row['product_id'],
                "title": row['title'],
                "description": row['description'],
                "price": float(row['price']) if row['price'] else None,
                "vendor": row['vendor'],
                "has_embedding": row['has_embedding'],
                "needs_resync": row['metadata'].get('needs_resync', False) if (row['metadata'] and isinstance(row['metadata'], dict)) else False,
                "updated_at": row['updated_at'].isoformat() if row['updated_at'] else None,
                "status": "ready" if row['has_embedding'] else "needs_sync"
            }
            for row in rows
        ]
    
    async def get_app_config(self, key: str = "ai_search") -> Dict:
        """Get app configuration from database"""
        pool = await self.connect()
        
        query = "SELECT value FROM app_settings WHERE key = $1"
        
        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, key)
            
        if row:
            # row['value'] is already a dict from JSONB type
            return row['value'] if isinstance(row['value'], dict) else json.loads(row['value'])
        
        # Return defaults if not found
        return {
            "ai_search_enabled": True,
            "autocorrect": True,
            "results_limit": "unlimited",  # Changed from "10" to match Shopify default behavior
            "similarity_threshold": 50,  # Lowered from 70 for better recall
            "exclude_out_of_stock": False,
            "exclude_archived": False,
            "language": "es"
        }
    
    async def save_app_config(self, config: Dict, key: str = "ai_search") -> bool:
        """Save app configuration to database"""
        pool = await self.connect()
        
        query = """
            INSERT INTO app_settings (key, value, description, updated_at)
            VALUES ($1, $2::jsonb, $3, CURRENT_TIMESTAMP)
            ON CONFLICT (key) 
            DO UPDATE SET 
                value = $2::jsonb,
                updated_at = CURRENT_TIMESTAMP
        """
        
        async with pool.acquire() as conn:
            await conn.execute(
                query, 
                key, 
                json.dumps(config),
                "AI search configuration settings"
            )
            
        print(f"✅ Saved configuration to database: {key}")
        return True


# Global instance
db_client = DatabaseClient()
