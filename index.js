const express = require('express');
const fs = require('fs');
const path = require('path');
const csv = require('csv-parser');

const app = express();
const port = 3000; // Bạn có thể đổi cổng nếu cần

// Đọc file config một lần khi server khởi động
let configData;
try {
    const configPath = path.join(__dirname, 'config.json');
    configData = JSON.parse(fs.readFileSync(configPath, 'utf8'));
} catch (err) {
    console.error('Lỗi khi đọc hoặc parse file config.json:', err);
    process.exit(1); // Thoát nếu không đọc được config
}

// Middleware để phục vụ các file tĩnh (index.html, bundle.min.js)
app.use(express.static(__dirname));

// API endpoint để lấy dữ liệu OHLCV
app.get('/api/ohlcv/:symbol/:timeframe', (req, res) => {
    const symbol = req.params.symbol.toLowerCase(); // Chuẩn hóa thành chữ thường
    const timeframe = req.params.timeframe.toLowerCase();
    const limit = parseInt(req.query.limit, 10); // Lấy limit từ query string

    console.log(`Yêu cầu dữ liệu cho: Symbol=${symbol}, Timeframe=${timeframe}, Limit=${limit || 'Tất cả'}`);

    // Tìm thông tin symbol và timeframe trong config
    const marketInfo = configData?.exchange?.binance?.marketdata?.[symbol];
    if (!marketInfo) {
        console.error(`Không tìm thấy symbol: ${symbol}`);
        return res.status(404).json({ error: `Symbol '${symbol}' không tồn tại trong config.` });
    }

    const timeframeData = marketInfo.data.find(d => d.name.toLowerCase() === timeframe);
    if (!timeframeData || !timeframeData.datalink) {
        console.error(`Không tìm thấy timeframe '${timeframe}' cho symbol '${symbol}' hoặc thiếu datalink.`);
        return res.status(404).json({ error: `Timeframe '${timeframe}' không tồn tại hoặc thiếu datalink cho symbol '${symbol}'.` });
    }

    const csvFileName = timeframeData.datalink;
    const csvFilePath = path.join(__dirname, 'binance_futures_data', 'binance_'+csvFileName);

    console.log(`Đang đọc file CSV: ${csvFilePath}`);

    const results = [];

    fs.createReadStream(csvFilePath)
        .pipe(csv())
        .on('data', (data) => results.push(data))
        .on('end', () => {
            console.log(`Đọc xong file CSV. Tổng số dòng: ${results.length}`);
            let responseData = results;
            if (!isNaN(limit) && limit > 0 && limit < results.length) {
                // Lấy 'limit' dòng cuối cùng
                responseData = results.slice(-limit);
                console.log(`Áp dụng limit=${limit}. Số dòng trả về: ${responseData.length}`);
            } else if (limit >= results.length) {
                 console.log(`Limit >= tổng số dòng. Trả về tất cả ${results.length} dòng.`);
                 responseData = results; // Trả về tất cả nếu limit >= số dòng
            } else {
                 console.log(`Không có limit hợp lệ hoặc limit <= 0. Trả về tất cả ${results.length} dòng.`);
                 responseData = results; // Trả về tất cả nếu không có limit hợp lệ
            }

            res.json(responseData);
        })
        .on('error', (error) => {
            console.error('Lỗi khi đọc file CSV:', error);
            // Kiểm tra xem lỗi có phải là ENOENT (File not found) không
            if (error.code === 'ENOENT') {
                 res.status(404).json({ error: `Không tìm thấy file CSV: ${csvFileName}` });
            } else {
                 res.status(500).json({ error: 'Lỗi server khi đọc dữ liệu CSV.' });
            }
        });
});

// Phục vụ file index.html cho route gốc
app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'index.html'));
});

app.listen(port, () => {
    console.log(`Server đang chạy tại http://localhost:${port}`);
});