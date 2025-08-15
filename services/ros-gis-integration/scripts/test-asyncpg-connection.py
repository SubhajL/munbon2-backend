#!/usr/bin/env python3

import asyncio
import asyncpg
import urllib.parse
import os

async def test_connection():
    try:
        # Get connection info from environment
        postgres_url = os.getenv('POSTGRES_URL', 'postgresql://postgres:P@ssw0rd123!@localhost:5432/munbon_dev')
        print(f"Original URL: {postgres_url}")
        
        # Parse the URL and rebuild with encoded password
        from urllib.parse import urlparse, urlunparse, quote
        parsed = urlparse(postgres_url)
        
        # Encode the password
        if parsed.password:
            encoded_password = quote(parsed.password, safe='')
            # Rebuild the netloc with encoded password
            netloc = f"{parsed.username}:{encoded_password}@{parsed.hostname}"
            if parsed.port:
                netloc += f":{parsed.port}"
            
            # Rebuild the URL
            encoded_url = urlunparse((
                parsed.scheme,
                netloc,
                parsed.path,
                parsed.params,
                parsed.query,
                parsed.fragment
            ))
            print(f"Encoded URL: {encoded_url}")
        else:
            encoded_url = postgres_url
        
        # Test direct connection
        print("\nTesting direct asyncpg connection...")
        conn = await asyncpg.connect(encoded_url)
        result = await conn.fetchval('SELECT version()')
        print(f"Success! PostgreSQL version: {result}")
        await conn.close()
        
        # Test pool creation
        print("\nTesting asyncpg pool creation...")
        pool = await asyncpg.create_pool(
            encoded_url,
            min_size=2,
            max_size=5
        )
        async with pool.acquire() as conn:
            result = await conn.fetchval('SELECT current_database()')
            print(f"Success! Connected to database: {result}")
        await pool.close()
        
        print("\nAll tests passed!")
        
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_connection())