const fs = require('fs');
const readline = require('readline');
const path = require('path');
const http = require('http');

const DATA_FILE = '/app/data/data.jsonl';
const PORT = 8080;

// Tres mapas para mantener los rankings separados
const wordFreq = {
    all: new Map(),
    python: new Map(),
    java: new Map()
};

let currentSize = 0;
let sseClients = [];

let stats = {
    totalWords: 0,
    reposProcessed: 0,
    filesProcessed: 0
};

function processLine(line) {
    try {
        if (!line.trim()) return;
        const data = JSON.parse(line);
        
        if (data.type === 'meta') {
            stats.reposProcessed++;
            stats.filesProcessed += data.files_processed;
        } 
        else if (data.word && data.lang) {
            stats.totalWords++;
            wordFreq.all.set(data.word, (wordFreq.all.get(data.word) || 0) + 1);
            wordFreq[data.lang].set(data.word, (wordFreq[data.lang].get(data.word) || 0) + 1);
        }
    } catch (err) {}
}

function getTopWords(map) {
    return Array.from(map.entries())
        .sort((a, b) => b[1] - a[1])
        .slice(0, 100)
        .map(([word, count]) => ({ word, count }));
}

function tailFile() {
    try {
        if (!fs.existsSync(DATA_FILE)) return;
        const stats = fs.statSync(DATA_FILE);
        
        if (stats.size > currentSize) {
            const stream = fs.createReadStream(DATA_FILE, { encoding: 'utf-8', start: currentSize, end: stats.size });
            const rl = readline.createInterface({ input: stream, crlfDelay: Infinity });
            rl.on('line', processLine);
            rl.on('close', () => { currentSize = stats.size; });
        } else if (stats.size < currentSize) {
            currentSize = 0;
            wordFreq.all.clear(); wordFreq.python.clear(); wordFreq.java.clear();
        }
    } catch (err) {}
}

setInterval(tailFile, 1000);

setInterval(() => {
    if (sseClients.length === 0) return;
    // Ahora enviamos un objeto con las 3 categorías listas
    const payload = JSON.stringify({
        stats: stats,
        all: getTopWords(wordFreq.all),
        python: getTopWords(wordFreq.python),
        java: getTopWords(wordFreq.java)
    });
    sseClients.forEach(client => client.write(`data: ${payload}\n\n`));
}, 2000);

const server = http.createServer((req, res) => {
    if (req.url === '/') {
        res.writeHead(200, { 'Content-Type': 'text/html' });
        res.end(fs.readFileSync(path.join(__dirname, 'index.html')));
    } else if (req.url === '/stream') {
        res.writeHead(200, { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache', 'Connection': 'keep-alive' });
        sseClients.push(res);
        req.on('close', () => { sseClients = sseClients.filter(c => c !== res); });
    } else {
        res.writeHead(404);
        res.end('Not Found');
    }
});

const dir = path.dirname(DATA_FILE);
if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });

server.listen(PORT, () => console.log(`Servidor Web en puerto ${PORT}`));