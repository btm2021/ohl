const express = require('express');
const fs = require('fs');
const path = require('path');
const csv = require('csv-parser');
const { pipeline } = require('stream/promises');
const zlib = require('zlib');

const app = express();
const port = process.env.PORT || 3000;
app.use(express.static(path.join(__dirname, 'public'), {
    setHeaders: (res) => {
        res.set('Cache-Control', 'public, max-age=3600');
    }
}));
// 1. Cấu hình nâng cao
const config = {
    maxLimit: 1000000,
    cacheTTL: 300000 // 5 phút
};

// 2. Cache dữ liệu
const dataCache = new Map();

// 3. Đọc cấu hình với async/await
async function loadConfig() {
    try {
        const configPath = path.resolve(__dirname, 'config.json');
        const rawData = await fs.promises.readFile(configPath, 'utf8');
        return JSON.parse(rawData);
    } catch (error) {
        console.error('Lỗi khởi tạo hệ thống:', error);
        process.exit(1);
    }
}

// 4. Middleware xác thực


// 5. Xử lý dữ liệu CSV với Stream
async function processCSV(filePath, limit) {
    return new Promise(async (resolve, reject) => {
        try {
            const results = [];
            const readStream = fs.createReadStream(filePath);
            
            // Tạo danh sách stream động
            const streams = [readStream];
            
            // Thêm stream giải nén nếu là file .gz
            if (filePath.endsWith('.gz')) {
                streams.push(zlib.createGunzip());
            }

            const csvStream = csv()
                .on('data', (data) => {
                    results.push(data);
                    // Giữ chỉ số lượng bản ghi được yêu cầu (lấy từ cuối file)
                    if (results.length > limit) results.shift();
                })
                .on('end', () => {
                    // Đảo ngược để đúng thứ tự thời gian (từ cũ đến mới)
                    resolve(results.reverse());
                })
                .on('error', reject);

            streams.push(csvStream);
            
            // Sử dụng pipeline với danh sách stream đã điều chỉnh
            await pipeline(...streams.filter(Boolean)); // Lọc bỏ giá trị null/undefined
            
        } catch (error) {
            reject(new Error(`Xử lý CSV thất bại: ${error.message}`));
        }
    });
}
// 6. Khởi tạo server
async function initializeServer() {
    const configData = await loadConfig();

    app.use(express.static(__dirname, {
        setHeaders: (res) => {
            res.set('Cache-Control', 'public, max-age=3600');
        }
    }));

    // Thêm route mới trước các route khác
app.get('/ohlcv', validateQueryParams, async (req, res) => {
    try {
        const { symbol, timeframe, limit } = req.query;
        const cacheKey = `${symbol}:${timeframe}:${limit}`;

        // Logic cache tương tự
        if (dataCache.has(cacheKey)) {
            const { data, timestamp } = dataCache.get(cacheKey);
            if (Date.now() - timestamp < config.cacheTTL) {
                return res.json(data);
            }
        }

        // Logic xử lý dữ liệu
        let s =symbol.toLowerCase()
        const market = configData.exchange.binance.marketdata[s]
        if (!market) throw new Error('Symbol not found');

        const timeframeData = market.data.find(d => d.name === timeframe);
        if (!timeframeData?.datalink) throw new Error('Invalid timeframe');

        const csvPath = path.resolve(
            __dirname,
            'binance_futures_data',
            `binance_${timeframeData.datalink}`
        );

        const data = await processCSV(csvPath, parseInt(limit, 10));
        dataCache.set(cacheKey, { 
            data, 
            timestamp: Date.now() 
        });

        res.json(data);
    } catch (error) {
        console.error(`[OHLCV Error] ${error.message}`);
        res.status(500).json({ error: error.message });
    }
});

// Middleware xác thực mới cho query params
function validateQueryParams(req, res, next) {
    const { symbol, timeframe, limit } = req.query;
    
    if (!symbol || !timeframe) {
        return res.status(400).json({ 
            error: "Missing required parameters: symbol, timeframe" 
        });
    }

    if (!/^[A-Z0-9]+$/.test(symbol)) {
        return res.status(400).json({ 
            error: "Invalid symbol format" 
        });
    }

    if (!/^\d+[mhdwM]$/.test(timeframe)) {
        return res.status(400).json({ 
            error: "Invalid timeframe format. Valid formats: 1m, 15m, 1h, 4h, 1d, 1w" 
        });
    }

    const parsedLimit = parseInt(limit, 10) || config.maxLimit;
    if (parsedLimit < 1 || parsedLimit > config.maxLimit) {
        return res.status(400).json({ 
            error: `Limit must be between 1 and ${config.maxLimit}` 
        });
    }

    req.processedParams = {
        symbol: symbol.toUpperCase(),
        timeframe,
        limit: parsedLimit
    };
    next();
}

    app.listen(port, () => {
        console.log(`Server đang chạy trên cổng ${port}`);
        console.log(`Chế độ: ${process.env.NODE_ENV || 'development'}`);
    });
}

initializeServer().catch(error => {
    console.error('Khởi động server thất bại:', error);
    process.exit(1);
});