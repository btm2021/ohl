import { existsSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

// --- Cấu hình ---
const PORT = process.env.PORT || 3000;
const CONFIG_FILE = 'config.json';
const DATA_DIR = 'binance_futures_data'; // Thư mục chứa các file CSV

// --- Lấy đường dẫn tuyệt đối ---
// Cần thiết để Bun biết vị trí file khi chạy script
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const configPath = resolve(__dirname, CONFIG_FILE);
const dataBasePath = resolve(__dirname + "/binance_futures_data", DATA_DIR);

// --- Hàm trợ giúp ---

// Load cấu hình
async function loadConfig() {
    try {
        const configFile = Bun.file(configPath);
        if (!(await configFile.exists())) {
            throw new Error(`Config file not found: ${configPath}`);
        }
        const configData = await configFile.json();
        console.log("Configuration loaded successfully.");
        return configData;
    } catch (error) {
        console.error("Error loading configuration:", error);
        // Thoát nếu không load được config, vì server không thể hoạt động
        process.exit(1);
    }
}

// Đọc và parse CSV
async function readCsvData(filePath) {
    try {
        const csvFile = Bun.file(filePath);
        if (!(await csvFile.exists())) {
            return { success: false, error: 'Data file not found', status: 404 };
        }

        const text = await csvFile.text();
        const lines = text.trim().split('\n');
        if (lines.length < 2) {
            return { success: false, error: 'CSV file is empty or has no data rows', status: 400 };
        }

        const header = lines[0].split(',').map(h => h.trim());
        const data = lines.slice(1).map(line => {
            const values = line.split(',');
            const row = {};
            header.forEach((col, index) => {
                // Chỉ lấy các cột cần thiết và chuyển đổi kiểu
                if (['open_time', 'open', 'high', 'low', 'close', 'volume'].includes(col)) {
                    const value = values[index] ? values[index].trim() : null;
                    if (col === 'open_time') {
                        // Giữ nguyên dạng chuỗi hoặc chuyển thành timestamp nếu cần
                        // Ví dụ chuyển thành timestamp (milliseconds):
                        // row[col] = value ? new Date(value).getTime() : null;
                        //row[col] = value; // Giữ nguyên string
                        row['timestamp']=value ? new Date(value).getTime() : null;
                    } else if (value !== null) {
                        row[col] = parseFloat(value); // Chuyển thành số
                    } else {
                        row[col] = null;
                    }
                }
            });
            return row;
        }).filter(row => Object.keys(row).length > 0); // Loại bỏ dòng trống có thể sinh ra do split

        return { success: true, data };

    } catch (error) {
        console.error(`Error reading or parsing CSV file ${filePath}:`, error);
        return { success: false, error: 'Error processing data file', status: 500 };
    }
}

// --- Khởi tạo Server ---

// Load config một lần khi server khởi động
const config = await loadConfig();

console.log(`Server starting on port ${PORT}...`);

Bun.serve({
    port: PORT,
    async fetch(req) {
        const url = new URL(req.url);

        // Chỉ xử lý route /ohlcv
        if (url.pathname !== '/ohlcv') {
            return new Response("Not Found", { status: 404 });
        }

        // Lấy query parameters
        const symbol = url.searchParams.get('symbol')?.toLowerCase();
        const timeframe = url.searchParams.get('timeframe');
        const limitParam = url.searchParams.get('limit');

        // --- Validation đầu vào ---
        if (!symbol || !timeframe) {
            return new Response(JSON.stringify({ success: false, error: 'Missing required parameters: symbol, timeframe' }), {
                status: 400,
                headers: { 'Content-Type': 'application/json' }
            });
        }

        let limit = undefined;
        if (limitParam) {
            limit = parseInt(limitParam, 10);
            if (isNaN(limit) || limit <= 0) {
                return new Response(JSON.stringify({ success: false, error: 'Invalid limit parameter: must be a positive integer' }), {
                    status: 400,
                    headers: { 'Content-Type': 'application/json' }
                });
            }
        }
        // --- Tìm kiếm trong config ---
        const exchangeData = config?.exchange?.binance?.marketdata;


        const symbolConfig = exchangeData[symbol];
        const timeframeData = symbolConfig.data?.find(d => d.name === timeframe);

        if (!timeframeData || !timeframeData.datalink) {
            return new Response(JSON.stringify({ success: false, error: `Timeframe '${timeframe}' not found for symbol '${symbol.toUpperCase()}'` }), {
                status: 404,
                headers: { 'Content-Type': 'application/json' }
            });
        }
        // --- Đọc dữ liệu CSV ---
        console.log('./binance_futures_data/'+timeframeData.datalink)
        const csvResult = await readCsvData("./binance_futures_data/binance_"+timeframeData.datalink);
       
        if (!csvResult.success) {
            return new Response(JSON.stringify({ success: false, error: csvResult.error }), {
                status: csvResult.status,
                headers: { 'Content-Type': 'application/json' }
            });
        }

        let responseData = csvResult.data;

        // Áp dụng limit nếu có
        if (limit && responseData.length > limit) {
            responseData = responseData.slice(-limit); // Lấy 'limit' phần tử cuối
        }

        // --- Trả về kết quả ---
        return new Response(JSON.stringify({ success: true, data: responseData }), {
            status: 200,
            headers: { 'Content-Type': 'application/json' }
        });
    },
    error(error) {
        console.error("Server Error:", error);
        return new Response("Internal Server Error", { status: 500 });
    },
});

console.log(`API server listening on http://localhost:${PORT}/ohlcv`);
console.log("Example: http://localhost:3000/ohlcv?symbol=BTCUSDT&timeframe=15m&limit=10");