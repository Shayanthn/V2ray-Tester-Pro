import asyncio
import aiohttp
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.enterprise_config import EnterpriseConfig

async def test_sources():
    print("--- Starting Source Validation ---")
    
    try:
        config = EnterpriseConfig()
        sources = config.DIRECT_CONFIG_SOURCES
        print(f"Successfully loaded configuration.")
        print(f"Total Direct Config Sources: {len(sources)}")
        
        if not sources:
            print("ERROR: No sources found!")
            return

        # Test a sample of sources (first 2, middle 2, last 2)
        indices = [0, 1, len(sources)//2, len(sources)//2 + 1, len(sources)-2, len(sources)-1]
        # Filter valid indices
        indices = sorted(list(set([i for i in indices if 0 <= i < len(sources)])))
        
        print(f"\nTesting reachability for {len(indices)} sample sources...")
        
        async with aiohttp.ClientSession() as session:
            for i in indices:
                url = sources[i]
                print(f"\nChecking Source #{i+1}: {url}")
                try:
                    async with session.get(url, timeout=10) as response:
                        print(f"  Status: {response.status}")
                        if response.status == 200:
                            content = await response.text()
                            preview = content[:50].replace('\n', ' ')
                            print(f"  Content Preview: {preview}...")
                            print("  [SUCCESS] Reachable")
                        else:
                            print("  [FAILURE] Non-200 Status")
                except Exception as e:
                    print(f"  [ERROR] Connection failed: {str(e)}")

    except Exception as e:
        print(f"CRITICAL ERROR: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_sources())
