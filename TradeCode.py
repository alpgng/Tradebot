from binance.client import Client
import numpy as np
NaN = np.nan

import pandas_ta as ta
import pandas as pd
import time

# Binance API Keys
API_KEY = 'your_api_key'  # Binance API anahtarınızı buraya ekleyin
API_SECRET = 'your_api_secret'  # Binance API secret anahtarınızı buraya ekleyin

# Binance Client Bağlantısı
client = Client(API_KEY, API_SECRET)

# Geçmiş Verileri Çekme
def get_historical_data(symbol, interval, lookback):
    klines = client.get_historical_klines(symbol, interval, lookback)
    df = pd.DataFrame(klines, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_asset_volume', 'number_of_trades',
        'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
    ])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    df = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
    return df

# Teknik İndikatörler
def add_indicators(data):
    # SMA ve EMA
    data['SMA_50'] = ta.sma(data['close'], length=50)
    data['SMA_200'] = ta.sma(data['close'], length=200)
    data['EMA_20'] = ta.ema(data['close'], length=20)
    
    # RSI
    data['RSI'] = ta.rsi(data['close'], length=14)
    
    # Bollinger Bands
    bb = ta.bbands(data['close'], length=20, std=2)
    data['BB_High'] = bb['BBL_20_2.0']
    data['BB_Low'] = bb['BBU_20_2.0']
    data['BB_Mid'] = bb['BBM_20_2.0']
    
    # MACD
    macd = data.ta.macd(fast=12, slow=26, signal=9, append=True)
    data['MACD'] = macd['MACD_12_26_9']
    data['MACD_Signal'] = macd['MACDs_12_26_9']
    data['MACD_Hist'] = macd['MACDh_12_26_9']

    
    # Stochastic Oscillator
    stoch = ta.stoch(data['high'], data['low'], data['close'], 14, 3, 3)
    print(stoch.tail())  # Son 5 satırı kontrol et

    # 'STOCHk_14_3' sütununun olup olmadığını kontrol et
    if 'STOCHk_14_3' in stoch.columns:
        data['Stoch_K'] = stoch['STOCHk_14_3']
    else:
        print("STOCHk_14_3 sütunu bulunamadı!")
    
    # ATR
    data['ATR'] = ta.atr(data['high'], data['low'], data['close'], length=14)
    
    return data

# Trade Sinyallerini Kontrol Etme
def check_trade_signals(data):
    last_row = data.iloc[-1]
    signals = []
    
    # Golden Cross
    if last_row['SMA_50'] > last_row['SMA_200']:
        signals.append("Golden Cross: Alım sinyali")
    
    # Bollinger Bands
    if last_row['close'] < last_row['BB_Low']:
        signals.append("Fiyat Bollinger Alt Bandında: Alım fırsatı")
    elif last_row['close'] > last_row['BB_High']:
        signals.append("Fiyat Bollinger Üst Bandında: Satış fırsatı")
    
    # RSI
    if last_row['RSI'] < 30:
        signals.append("RSI Aşırı Satış: Alım sinyali")
    elif last_row['RSI'] > 70:
        signals.append("RSI Aşırı Alım: Satış sinyali")
    
    # MACD
    if last_row['MACD'] > last_row['MACD_Signal']:
        signals.append("MACD Pozitif Kesişim: Alım sinyali")
    elif last_row['MACD'] < last_row['MACD_Signal']:
        signals.append("MACD Negatif Kesişim: Satış sinyali")
    
    return signals

# Alım-Satım İşlemleri
def place_order(symbol, side, quantity):
    time.sleep(1)
    if side == 'BUY':
        order = client.order_market_buy(symbol=symbol, quantity=quantity)
    elif side == 'SELL':
        order = client.order_market_sell(symbol=symbol, quantity=quantity)
    print(order)

# Bot Döngüsü
def trade_bot(symbol, interval, lookback, quantity):
    while True:
        print(f"Processing data for {symbol}...")
        data = get_historical_data(symbol, interval, lookback)
        data = add_indicators(data)
        
        signals = check_trade_signals(data)
        for signal in signals:
            print(signal)
            if "Alım" in signal:
                place_order(symbol, 'BUY', quantity)
            elif "Satış" in signal:
                place_order(symbol, 'SELL', quantity)
        
        print("Bekleniyor...")
        time.sleep(60 * 60)  # 1 saat bekle

# Botu Başlatma
if __name__ == "__main__":
    trade_bot(symbol='BTCUSDT', interval='1h', lookback='30 days ago UTC', quantity=0.001)
server_time = client.get_server_time()  # Binance sunucusunun zamanını alın
print(server_time)
