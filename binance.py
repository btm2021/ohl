import os
import pandas as pd
import numpy as np
import time
import requests
import json
import glob
from datetime import datetime, timedelta
from tqdm import tqdm
from colorama import Fore, Style, init

# Khởi tạo colorama
init(autoreset=True)

# Thư mục lưu dữ liệu
DATA_DIRECTORY = "binance_futures_data"
# Khung thời gian mặc định
#DEFAULT_TIMEFRAMES = ['5m', '15m', '1h', '4h']
DEFAULT_TIMEFRAMES = ['15m']

# File cấu hình
CONFIG_FILE = "config.json"

def create_directory(directory):
    """
    Tạo thư mục nếu chưa tồn tại
    """
    if not os.path.exists(directory):
        os.makedirs(directory)
        print(f"{Fore.GREEN}Đã tạo thư mục {directory}{Style.RESET_ALL}")

def get_all_futures_symbols():
    """
    Lấy tất cả các symbol đang giao dịch trên Binance Futures, chỉ lọc các cặp USDT
    """
    url = 'https://fapi.binance.com/fapi/v1/exchangeInfo'
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        symbols = []
        symbol_info_dict = {}
        
        for symbol_info in data['symbols']:
            if symbol_info['status'] == 'TRADING' and symbol_info['quoteAsset'] == 'USDT':
                symbols.append(symbol_info['symbol'])
                symbol_info_dict[symbol_info['symbol']] = symbol_info
        
        print(f"{Fore.CYAN}Đã tìm thấy {len(symbols)} cặp USDT đang giao dịch trên Binance Futures{Style.RESET_ALL}")
        return symbols, symbol_info_dict, data
    except Exception as e:
        print(f"{Fore.RED}Lỗi khi lấy danh sách symbol: {e}{Style.RESET_ALL}")
        return [], {}, {}

def get_earliest_timestamp(symbol, interval):
    """
    Lấy timestamp của thời điểm đầu tiên một symbol future được niêm yết trên Binance
    """
    url = f'https://fapi.binance.com/fapi/v1/klines'
    params = {
        'symbol': symbol,
        'interval': interval,
        'limit': 1,
        'startTime': 0  # bắt đầu từ timestamp 0 để tìm dữ liệu đầu tiên có sẵn
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        klines = response.json()
        if klines:
            return klines[0][0]  # timestamp đầu tiên có sẵn
    except Exception as e:
        print(f"{Fore.RED}Lỗi khi lấy timestamp đầu tiên cho {symbol}: {e}{Style.RESET_ALL}")
    
    return None

def get_interval_ms(interval):
    """
    Chuyển đổi khoảng thời gian sang miligiây
    """
    interval_dict = {
        '1m': 60 * 1000,
        '3m': 3 * 60 * 1000,
        '5m': 5 * 60 * 1000,
        '15m': 15 * 60 * 1000,
        '30m': 30 * 60 * 1000,
        '1h': 60 * 60 * 1000,
        '2h': 2 * 60 * 60 * 1000,
        '4h': 4 * 60 * 60 * 1000,
        '6h': 6 * 60 * 60 * 1000,
        '8h': 8 * 60 * 60 * 1000,
        '12h': 12 * 60 * 60 * 1000,
        '1d': 24 * 60 * 60 * 1000,
        '3d': 3 * 24 * 60 * 60 * 1000,
        '1w': 7 * 24 * 60 * 60 * 1000,
        '1M': 30 * 24 * 60 * 60 * 1000
    }
    return interval_dict.get(interval, 24 * 60 * 60 * 1000)  # Mặc định là 1 ngày

def load_config():
    """
    Đọc file cấu hình nếu tồn tại, nếu không thì tạo mới
    """
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                print(f"{Fore.GREEN}Đã đọc file cấu hình {CONFIG_FILE}{Style.RESET_ALL}")
                return config
        except Exception as e:
            print(f"{Fore.RED}Lỗi khi đọc file cấu hình: {e}. Tạo file mới.{Style.RESET_ALL}")
    
    # Tạo cấu trúc mới nếu file không tồn tại hoặc có lỗi
    config = {
        "exchange": {
            "binance": {
                "datatype": "crypto",
                "markettype": "future",
                "marketdata": {}
            }
        }
    }
    
    # Lưu file cấu hình mới
    save_config(config)
    print(f"{Fore.GREEN}Đã tạo file cấu hình mới {CONFIG_FILE}{Style.RESET_ALL}")
    
    return config

def save_config(config):
    """
    Lưu cấu hình vào file
    """
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
            print(f"{Fore.GREEN}Đã lưu file cấu hình {CONFIG_FILE}{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}Lỗi khi lưu file cấu hình: {e}{Style.RESET_ALL}")

def get_crypto_icon_url(symbol):
    """
    Tạo URL cho biểu tượng của cryptocurrency
    """
    symbol_lower = symbol.lower()
    return f"https://github.com/spothq/cryptocurrency-icons/blob/master/128/icon/{symbol_lower}.png"

def extract_symbol_pair(symbol):
    """
    Tách symbol thành base và quote currency
    Ví dụ: BTCUSDT -> BTC, USDT
    """
    # Đối với cặp USDT, đơn giản là tách phần USDT ra khỏi symbol
    if symbol.endswith('USDT'):
        base = symbol[:-4]
        return base, 'USDT'
    
    # Trường hợp khác (không nên xảy ra vì chúng ta đã lọc)
    return symbol[:-4], symbol[-4:]

def update_config_for_symbol(config, symbol, timeframe, filename, symbol_info=None, start_date=None, end_date=None):
    """
    Cập nhật cấu hình cho một symbol và timeframe, bao gồm thông tin chi tiết từ exchangeInfo
    """
    base_symbol, quote_pair = extract_symbol_pair(symbol)
    
    # Chuyển symbol về chữ thường để sử dụng làm key
    symbol_key = symbol.lower()
    
    # Lấy đối tượng marketdata
    marketdata = config["exchange"]["binance"]["marketdata"]
    
    # Nếu symbol chưa tồn tại trong cấu hình, thêm mới
    if symbol_key not in marketdata:
        print(f"{Fore.YELLOW}Thêm symbol mới {symbol} vào cấu hình{Style.RESET_ALL}")
        
        # Tạo cấu trúc cơ bản
        marketdata[symbol_key] = {
            "symbol": base_symbol,
            "pair": quote_pair,
            "fullname": symbol,
            "icon": get_crypto_icon_url(base_symbol),
            "data": []
        }
        
        # Thêm thông tin chi tiết của symbol nếu có
        if symbol_info:
            marketdata[symbol_key]["symbolDesc"] = symbol_info
    
    # Kiểm tra xem timeframe đã tồn tại chưa
    timeframe_exists = False
    for tf_data in marketdata[symbol_key]["data"]:
        if tf_data["name"] == timeframe:
            # Cập nhật thông tin timeframe
            tf_data["datalink"] = f"{symbol}_{timeframe}.csv"
            if start_date:
                tf_data["fromdate"] = start_date
            if end_date:
                tf_data["enddate"] = end_date
            timeframe_exists = True
            break
    
    # Nếu timeframe chưa tồn tại, thêm mới
    if not timeframe_exists:
        print(f"{Fore.YELLOW}Thêm timeframe mới {timeframe} cho {symbol} vào cấu hình{Style.RESET_ALL}")
        marketdata[symbol_key]["data"].append({
            "name": timeframe,
            "datalink": f"{symbol}_{timeframe}.csv",
            "fromdate": start_date if start_date else "",
            "enddate": end_date if end_date else ""
        })
    
    return config

def get_symbol_timeframe_info(config, symbol, timeframe):
    """
    Lấy thông tin về symbol và timeframe từ cấu hình
    """
    symbol_key = symbol.lower()
    
    try:
        marketdata = config["exchange"]["binance"]["marketdata"]
        if symbol_key in marketdata:
            for tf_data in marketdata[symbol_key]["data"]:
                if tf_data["name"] == timeframe:
                    return tf_data
    except Exception as e:
        print(f"{Fore.RED}Lỗi khi đọc thông tin symbol {symbol}, timeframe {timeframe}: {e}{Style.RESET_ALL}")
    
    return None

def check_existing_files(symbol, timeframe):
    """
    Kiểm tra xem dữ liệu cho symbol và timeframe đã tồn tại chưa
    """
    # Đảm bảo thư mục tồn tại
    create_directory(DATA_DIRECTORY)
    
    # Tìm kiếm các file khớp với pattern
    pattern = f"{DATA_DIRECTORY}/binance_{symbol}_{timeframe}_*.csv"
    existing_files = glob.glob(pattern)
    
    return existing_files

def get_download_list(symbols, timeframes, config, symbol_info_dict):
    """
    Tạo danh sách các cặp symbol-timeframe cần tải
    """
    download_list = []
    update_list = []
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Kiểm tra từng cặp symbol-timeframe
    for symbol in symbols:
        for timeframe in timeframes:
            symbol_tf_info = get_symbol_timeframe_info(config, symbol, timeframe)
            
            if symbol_tf_info is None:
                # Symbol hoặc timeframe chưa có trong cấu hình
                download_list.append((symbol, timeframe, None, None, symbol_info_dict.get(symbol)))
                print(f"{Fore.CYAN}Thêm {symbol} ({timeframe}) vào danh sách tải mới{Style.RESET_ALL}")
            elif symbol_tf_info["enddate"] != today:
                # Symbol đã có nhưng cần cập nhật
                start_date = symbol_tf_info["enddate"]
                # Nếu enddate rỗng, tải toàn bộ dữ liệu
                if not start_date:
                    download_list.append((symbol, timeframe, None, None, symbol_info_dict.get(symbol)))
                    print(f"{Fore.CYAN}Thêm {symbol} ({timeframe}) vào danh sách tải mới (không có dữ liệu){Style.RESET_ALL}")
                else:
                    # Chuyển đổi string date sang datetime
                    start_date_dt = datetime.strptime(start_date, '%Y-%m-%d')
                    # Cộng thêm 1 ngày để không tải trùng dữ liệu
                    start_date_dt = start_date_dt + timedelta(days=1)
                    start_date_ts = int(start_date_dt.timestamp() * 1000)
                    update_list.append((symbol, timeframe, start_date_ts, None, symbol_info_dict.get(symbol)))
                    print(f"{Fore.CYAN}Thêm {symbol} ({timeframe}) vào danh sách cập nhật từ {start_date_dt.strftime('%Y-%m-%d')}{Style.RESET_ALL}")
            else:
                print(f"{Fore.GREEN}{symbol} ({timeframe}) đã cập nhật đến ngày hôm nay{Style.RESET_ALL}")
    
    return download_list, update_list

def download_futures_data(symbol, interval='1d', start_time=None, end_time=None, retry_count=3):
    """
    Tải xuống dữ liệu futures của Binance cho một symbol
    
    Parameters:
    symbol (str): Symbol cần lấy dữ liệu (ví dụ: 'BTCUSDT')
    interval (str): Khoảng thời gian của candlestick
    start_time (int): Timestamp (ms) bắt đầu
    end_time (int): Timestamp (ms) kết thúc (mặc định: thời gian hiện tại)
    retry_count (int): Số lần thử lại nếu gặp lỗi
    
    Returns:
    pandas.DataFrame: DataFrame chứa dữ liệu
    """
    # Nếu không cung cấp thời gian kết thúc, sử dụng thời gian hiện tại
    if end_time is None:
        end_time = int(datetime.now().timestamp() * 1000)
    
    # Nếu không cung cấp thời gian bắt đầu, lấy thời gian đầu tiên của symbol
    if start_time is None:
        start_time = get_earliest_timestamp(symbol, interval)
        if start_time is None:
            print(f"{Fore.RED}Không thể lấy thời gian bắt đầu cho {symbol} với khung thời gian {interval}{Style.RESET_ALL}")
            return None
    
    # Khởi tạo DataFrame để lưu trữ dữ liệu
    all_data = []
    
    # Số lượng nến tối đa mà API cho phép trong một lần gọi
    limit = 1500
    
    # Tải dữ liệu lần lượt
    current_start = start_time
    
    start_date = datetime.fromtimestamp(start_time/1000).strftime('%Y-%m-%d')
    
    # Tính tổng thời gian cần tải
    total_time_range = end_time - start_time
    # Ước tính số lần request cần thực hiện
    estimated_iterations = max(1, min(1000, (total_time_range // (limit * get_interval_ms(interval))) + 1))
    
    # Tạo progress bar
    progress_bar = tqdm(total=estimated_iterations, desc=f"{symbol} ({interval})", 
                        bar_format="{l_bar}%s{bar}%s{r_bar}" % (Fore.GREEN, Style.RESET_ALL))
    
    retries = 0
    while current_start < end_time:
        url = 'https://fapi.binance.com/fapi/v1/klines'
        params = {
            'symbol': symbol,
            'interval': interval,
            'startTime': current_start,
            'endTime': min(current_start + limit * get_interval_ms(interval), end_time),
            'limit': limit
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if not data:
                # Không còn dữ liệu
                break
            
            all_data.extend(data)
            
            # Cập nhật thời gian bắt đầu cho lần gọi tiếp theo
            current_start = data[-1][0] + 1
            
            # Cập nhật progress bar
            progress_bar.update(1)
            
            # Reset số lần thử lại
            retries = 0
            
            # Tạm dừng để tránh vượt quá giới hạn tốc độ của API
            time.sleep(0.1)
            
        except Exception as e:
            retries += 1
            if retries > retry_count:
                print(f"\n{Fore.RED}Đã thử lại {retry_count} lần nhưng không thành công: {e}{Style.RESET_ALL}")
                break
                
            print(f"\n{Fore.YELLOW}Lỗi khi tải dữ liệu {symbol} ({interval}): {e}. Thử lại lần {retries}/{retry_count}{Style.RESET_ALL}")
            # Tạm dừng lâu hơn nếu gặp lỗi
            time.sleep(2 * retries)
            continue
    
    progress_bar.close()
    
    if not all_data:
        print(f"{Fore.RED}Không có dữ liệu cho {symbol} với khung thời gian {interval}{Style.RESET_ALL}")
        return None
    
    # Chuyển đổi dữ liệu thành DataFrame
    df = pd.DataFrame(all_data, columns=[
        'open_time', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_asset_volume', 'number_of_trades',
        'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
    ])
    
    # Chuyển đổi kiểu dữ liệu
    numeric_columns = ['open', 'high', 'low', 'close', 'volume', 
                      'quote_asset_volume', 'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume']
    
    for col in numeric_columns:
        df[col] = pd.to_numeric(df[col])
    
    # Chuyển đổi timestamps thành datetime
    df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
    df['close_time'] = pd.to_datetime(df['close_time'], unit='ms')
    
    print(f"{Fore.GREEN}Hoàn thành! Đã tải xuống {len(df)} bản ghi cho {symbol} ({interval}){Style.RESET_ALL}")
    
    return df

def save_data_to_csv(df, symbol, interval, directory=DATA_DIRECTORY):
    """
    Lưu DataFrame vào file CSV
    """
    # Tạo thư mục nếu chưa tồn tại
    create_directory(directory)
    
    # Lấy thời gian kết thúc của dữ liệu để đặt tên file 
    filename = f"{directory}/binance_{symbol}_{interval}.csv"
    df.to_csv(filename, index=False)
    print(f"{Fore.GREEN}Đã lưu dữ liệu vào file {filename}{Style.RESET_ALL}")
    
    return filename

def update_config_from_data(config, df, symbol, timeframe, symbol_info=None):
    """
    Cập nhật thông tin trong config từ dữ liệu đã tải
    """
    # Lấy ngày bắt đầu và kết thúc từ DataFrame
    from_date = df['open_time'].min().strftime('%Y-%m-%d')
    end_date = df['close_time'].max().strftime('%Y-%m-%d')
    
    # Cập nhật config
    config = update_config_for_symbol(config, symbol, timeframe, f"{symbol}_{timeframe}.csv", symbol_info, from_date, end_date)
    
    return config

def auto_download_futures_data():
    """
    Tự động tải dữ liệu futures cho tất cả các symbol và timeframe, chỉ các cặp USDT
    """
    # Đọc file cấu hình
    config = load_config()
    
    # Lấy tất cả symbol đang giao dịch, chỉ lấy các cặp USDT và thông tin chi tiết
    symbols, symbol_info_dict, exchange_info = get_all_futures_symbols()
    
    # Tạo danh sách cần tải (chỉ những symbol và timeframe chưa tồn tại hoặc cần cập nhật)
    download_list, update_list = get_download_list(symbols, DEFAULT_TIMEFRAMES, config, symbol_info_dict)
    
    total_tasks = len(download_list) + len(update_list)
    if total_tasks == 0:
        print(f"{Fore.GREEN}Tất cả dữ liệu đã cập nhật đến ngày hôm nay. Không cần tải thêm.{Style.RESET_ALL}")
        return
    
    print(f"{Fore.CYAN}Cần tải {len(download_list)} cặp symbol-timeframe mới và cập nhật {len(update_list)} cặp{Style.RESET_ALL}")
    
    # Hiển thị danh sách các symbol và timeframe sẽ được tải
    new_symbol_count = len(set([item[0] for item in download_list]))
    update_symbol_count = len(set([item[0] for item in update_list]))
    print(f"{Fore.CYAN}Số lượng symbol cần tải mới: {new_symbol_count}, cần cập nhật: {update_symbol_count}{Style.RESET_ALL}")
    
    # Tạo thanh tiến trình tổng thể
    overall_progress = tqdm(total=total_tasks, desc="Tổng tiến độ", 
                           bar_format="{l_bar}%s{bar}%s{r_bar}" % (Fore.BLUE, Style.RESET_ALL))
    
    # Tải dữ liệu mới
    process_data_list(download_list, config, overall_progress, 0, "Tải mới")
    
    # Cập nhật dữ liệu
    process_data_list(update_list, config, overall_progress, len(download_list), "Cập nhật")
    
    overall_progress.close()
    print(f"{Fore.GREEN}Đã hoàn thành việc tải dữ liệu!{Style.RESET_ALL}")

def process_data_list(data_list, config, progress_bar, start_index, action_text):
    """
    Xử lý danh sách dữ liệu cần tải
    """
    for i, (symbol, timeframe, start_time, end_time, symbol_info) in enumerate(data_list):
        try:
            print(f"\n{Fore.YELLOW}[{i+1+start_index}/{progress_bar.total}] {action_text} dữ liệu cho {symbol} ({timeframe}){Style.RESET_ALL}")
            
            # Tải dữ liệu
            data = download_futures_data(symbol, timeframe, start_time, end_time)
            
            # Lưu dữ liệu và cập nhật cấu hình
            if data is not None and not data.empty:
                filename = save_data_to_csv(data, symbol, timeframe)
                config = update_config_from_data(config, data, symbol, timeframe, symbol_info)
                save_config(config)
            
        except Exception as e:
            print(f"{Fore.RED}Lỗi khi xử lý {symbol} ({timeframe}): {e}{Style.RESET_ALL}")
        
        # Cập nhật tiến trình tổng thể
        progress_bar.update(1)
        
        # Tạm dừng giữa các lần tải để tránh vượt quá giới hạn tốc độ API
        time.sleep(0.5)

def main():
    print(f"{Fore.CYAN}===== BINANCE FUTURES DATA DOWNLOADER ====={Style.RESET_ALL}")
    print(f"{Fore.CYAN}Script sẽ tự động tải dữ liệu cho các cặp USDT và timeframe chưa tồn tại{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Đồng thời cập nhật dữ liệu cho các symbol đã tồn tại nếu cần{Style.RESET_ALL}")
    
    # Đảm bảo thư mục dữ liệu tồn tại
    create_directory(DATA_DIRECTORY)
    
    # Bắt đầu tải dữ liệu tự động
    auto_download_futures_data()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Fore.RED}Đã hủy quá trình tải dữ liệu.{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}Lỗi không mong muốn: {e}{Style.RESET_ALL}")