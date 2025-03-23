
from flask import Flask, request, jsonify
import pandas as pd
import requests
import json
from datetime import datetime
import pytz

app = Flask(__name__)

@app.route('/api/data', methods=['GET'])
def get_data():
    # Lấy tham số từ request
    symbol = request.args.get('symbol', 'BTCUSDT')
    timeframe = request.args.get('timeframe', '15m')
    limit = int(request.args.get('limit', 100))
    
    # Tạo URL để lấy dữ liệu CSV từ GitHub
    base_url = "https://raw.githubusercontent.com/btm2021/ohl/master/binance_futures_data"
    csv_url = f"{base_url}/binance_{symbol}_{timeframe}.csv"
    
    # Lấy config từ GitHub
    config_url = "https://raw.githubusercontent.com/btm2021/ohl/master/config.json"
    
    try:
        # Đọc file CSV từ GitHub
        df = pd.read_csv(csv_url)
        
        # Lấy config từ GitHub
        config_response = requests.get(config_url)
        config_data = config_response.json()
        
        # Chỉ giữ lại số lượng dòng theo limit (từ cuối lên)
        if len(df) > limit:
            df = df.tail(limit)
        
        # Chuyển đổi cột open_time sang Unix timestamp
        df['timestamp'] = pd.to_datetime(df['open_time']).apply(lambda x: int(x.timestamp()))
        
        # Chỉ lấy các cột cần thiết
        selected_columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        data_list = df[selected_columns].values.tolist()
        
        # Lấy thông tin symbol từ config nếu có
        symbol_lower = symbol.lower()
        symbol_desc = {}
        market_data = {}
        print(data_list)
        if symbol_lower in config_data.get('marketdata', {}):
            symbol_desc = config_data['marketdata'][symbol_lower]['symbolDesc']
            
            # Tạo cấu trúc dữ liệu theo yêu cầu
            market_data[symbol_lower] = {
                "symbol": symbol_desc.get('baseAsset', symbol.upper().replace('USDT', '')),
                "pair": symbol_desc.get('quoteAsset', 'USDT'),
                "fullname": symbol.upper(),
                "icon": f"https://github.com/spothq/cryptocurrency-icons/blob/master/128/icon/{symbol_lower.replace('usdt', '')}.png",
                "symbolDesc": symbol_desc,
                "data": data_list
            }
        else:
            # Nếu không tìm thấy trong config, tạo dữ liệu mặc định
            symbol_base = symbol.upper().replace('USDT', '')
            market_data[symbol_lower] = {
                "symbol": symbol_base,
                "pair": "USDT",
                "fullname": symbol.upper(),
                "icon": f"https://github.com/spothq/cryptocurrency-icons/blob/master/128/icon/{symbol_lower.replace('usdt', '')}.png",
                "symbolDesc": {
                    "symbol": symbol.upper(),
                    "pair": symbol.upper(),
                    "baseAsset": symbol_base,
                    "quoteAsset": "USDT",
                },
                "data": data_list
            }
        
        # Tạo response JSON
        response = {
            "datatype": "crypto",
            "markettype": "future",
            "marketdata": market_data
        }
        
        return jsonify(response)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)