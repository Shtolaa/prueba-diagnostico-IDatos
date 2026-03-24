import os
import json
import asyncio
import ast
import re
import aiohttp
import aiofiles
from tenacity import retry, stop_after_attempt, wait_exponential_jitter

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
DATA_FILE = "/app/data/data.jsonl"
CONCURRENT_REQUESTS = 30

HEADERS = {"Accept": "application/vnd.github.v3+json"}
if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"token {GITHUB_TOKEN}"

# Regex para extraer firmas de métodos en Java
JAVA_METHOD_REGEX = re.compile(
    r'(?:public|protected|private|static|\s) +[\w\<\>\[\]]+\s+(\w+) *\([^\)]*\) *\{'
)

write_lock = asyncio.Lock()

@retry(stop=stop_after_attempt(5), wait=wait_exponential_jitter(initial=2, max=15))
async def fetch_json(session, url):
    async with session.get(url, headers=HEADERS) as response:
        if response.status == 403 or response.status == 429:
            print(f"[Rate Limit] Esperando para {url}...")
            response.raise_for_status()
        if response.status == 200:
            return await response.json()
        return None

@retry(stop=stop_after_attempt(3), wait=wait_exponential_jitter(initial=1, max=5))
async def fetch_text(session, url):
    async with session.get(url, headers=HEADERS) as response:
        if response.status == 200:
            try:
                # Leemos los bytes crudos y forzamos la decodificación ignorando caracteres rotos
                raw_bytes = await response.read()
                return raw_bytes.decode('utf-8', errors='ignore')
            except Exception:
                return None
        return None

def tokenize_name(name):
    """Separa palabras por camelCase y snake_case según el requerimiento."""
    # Ejemplo: make_response -> make, response | retainAll -> retain, all
    normalized = re.sub(r'([a-z])([A-Z])', r'\1 \2', name).replace('_', ' ')
    return [w.lower() for w in normalized.split() if len(w) > 1]

def extract_python(code):
    try:
        tree = ast.parse(code)
        return [node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    except:
        return []

def extract_java(code):
    return JAVA_METHOD_REGEX.findall(code)

async def process_file(session, repo, branch, file_path, semaphore):
    raw_url = f"https://raw.githubusercontent.com/{repo}/{branch}/{file_path}"
    async with semaphore:
        code = await fetch_text(session, raw_url)
    
    if not code: return

    lang = "python" if file_path.endswith('.py') else "java"
    raw_names = extract_python(code) if lang == "python" else extract_java(code)
    
    tokens = []
    for name in raw_names:
        tokens.extend(tokenize_name(name))

    if not tokens: return

    async with write_lock:
        async with aiofiles.open(DATA_FILE, mode='a', encoding='utf-8') as f:
            lines = [json.dumps({"word": token, "lang": lang}) + "\n" for token in tokens]
            await f.writelines(lines)

async def process_repo(session, repo, semaphore):
    print(f"[{repo}] Analizando...")
    repo_data = await fetch_json(session, f"https://api.github.com/repos/{repo}")
    if not repo_data: return
    branch = repo_data.get("default_branch", "main")

    tree_data = await fetch_json(session, f"https://api.github.com/repos/{repo}/git/trees/{branch}?recursive=1")
    if not tree_data or "tree" not in tree_data: return

    target_files = [
        item["path"] for item in tree_data["tree"] 
        if item["type"] == "blob" and (item["path"].endswith('.py') or item["path"].endswith('.java'))
    ]

    # Limitar a 50 archivos por repo para mantener el pipeline fluyendo rápido
    tasks = [process_file(session, repo, branch, path, semaphore) for path in target_files[:15]]
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    async with write_lock:
        async with aiofiles.open(DATA_FILE, mode='a', encoding='utf-8') as f:
            meta = {"type": "meta", "repo": repo, "files_processed": len(tasks)}
            await f.write(json.dumps(meta) + "\n")
            await f.flush()

async def main():
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    open(DATA_FILE, 'w').close()
    semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)
    
    connector = aiohttp.TCPConnector(limit=CONCURRENT_REQUESTS)
    async with aiohttp.ClientSession(connector=connector) as session:
        page = 1
        while True: # Ejecución continua
            print(f"\n=== Buscando repositorios Top (Página {page}) ===")
            search_url = f"https://api.github.com/search/repositories?q=language:python+language:java&sort=stars&order=desc&per_page=10&page={page}"
            search_data = await fetch_json(session, search_url)
            
            if not search_data or "items" not in search_data:
                await asyncio.sleep(60) # Esperar si se agota el rate limit global
                continue

            repos = [item["full_name"] for item in search_data["items"]]
            
            for repo in repos:
                await process_repo(session, repo, semaphore)
            
            page += 1

if __name__ == "__main__":
    asyncio.run(main())