import json
import sys
sys.path.insert(0, '.')

from bot_python.bot_1hz50v import hma, hma_direction

for symbol in ["1HZ10V", "1HZ25V", "1HZ50V", "1HZ75V"]:
    with open(f'real_{symbol}.json') as f:
        prices = json.load(f)
    
    candles = []
    for i in range(0, len(prices), 60):
        chunk = prices[i:i+60]
        if len(chunk) == 60:
            candles.append({"open": chunk[0], "high": max(chunk), "low": min(chunk), "close": chunk[-1]})
    
    # Calculate indicators
    closes = [c["close"] for c in candles]
    hma_vals = hma([c["close"] for c in candles], 30)
    hma_for_dir = hma([c["close"] for c in candles], 30)
    dir_vals = hma_direction(hma_for_dir)
    
    # Backtest
    stake = 10.0
    max_stake = 50.0
    balance = 5000
    martingale_step = 0
    last_exit = -1000
    trades = []
    position = None
    entry_price = 0
    entry_idx = 0
    stake_val = 10.0
    martingale_step = 0
    last_exit = -1000
    balance = 5000
    
    for i in range(len(candles)):
        if i < 150: continue
        
        candle = candles[i]
        price = candle["close"]
        d = dir_vals[i]
        if dir_vals[i] is None: continue
        
        hma_c = hma_vals[i]
        hma_p = hma[i-1] if i > 0 else hma_c
        hma_slope = hma_c - hma_p
        price_above = price > hma_c
        price_below = price < hma_c
        
        if i - last_exit < 10:
            if position and i - entry_idx >= 1:
                win = (price > entry_price) if position == "long" else (price < entry_price)
                pnl = stake * 0.80 if win else -stake
                balance += pnl
                trades.append({'win': win, 'pnl': pnl})
                if win: martingale_step = 0
                else: martingale_step += 1
                if martingale_step >= 3: martingale_step = 0
                stake = min(stake * 2, 50.0)
                last_exit = i
                position = None
            continue
        
        if position is None:
            stake = min(10 * (2 ** martingale_step), 50.0)
            hma_c = hma_vals[i]
            hma_p = hma[i-1] if i > 0 else hma_c
            hma_slope = hma_c - hma_p
            price_above = price > hma_c
            price_below = price < hma_c
            
            if d == 1 and price_above and hma_slope >= 0:
                position = "long"; entry_price = price; entry_idx = i
            elif d == -1 and price_below and hma_slope <= 0:
                position = "short"; entry_price = price; entry_idx = i
        
        if position and i - entry_idx >= 1:
            win = (price > entry_price) if position == "long" else (price < entry_price)
            pnl = stake * 0.80 if win else -stake
            balance += pnl
            trades.append({'win': win, 'pnl': pnl})
            if win: martingale_step = 0
            else: martingale_step += 1
            if martingale_step >= 3: martingale_step = 0
            stake = min(stake * 2, 50.0)
            last_exit = i
            position = None
    
    wins = sum(1 for t in trades if t['win'])
    losses = len(trades) - wins
    total_pnl = sum(t['pnl'] for t in trades)
    wr = (wins / len(trades) * 100) if trades else 0
    
    running = 0; peak = 0; max_dd = 0
    for t in trades:
        running += t['pnl']
        peak = max(peak, running)
        max_dd = max(max_dd, peak - running)
    
    freq = len(candles) / len(trades) if trades else 0
    print(f"  {symbol}: Trades={len(trades)} Freq=1/{len(candles)/len(trades):.1f} WR={wr:.1f}% PnL=${total_pnl:.2f} DD=${max_dd:.2f}")

# Run for each symbol
from bot_python.bot_1hz50v import hma, hma_direction

for symbol in ["1HZ10V", "1HZ25V", "1HZ50V", "1HZ75V"]:
    with open(f'real_{symbol}.json') as f:
        prices = json.load(f)
    
    candles = []
    for i in range(0, len(prices), 60):
        chunk = prices[i:i+60]
        if len(chunk) == 60:
            candles.append({"open": chunk[0], "high": max(chunk), "low": min(chunk), "close": chunk[-1]})
    
    # Calculate indicators
    closes = [c["close"] for c in candles]
    hma_vals = hma([c["close"] for c in candles], 30)
    hma_for_dir = hma([c["close"] for c in candles], 30)
    dir_vals = hma_direction(hma_for_dir)
    
    # Backtest
    stake = 10.0
    max_stake = 50.0
    balance = 5000
    martingale_step = 0
    last_exit = -1000
    trades = []
    position = None
    entry_price = 0
    entry_idx = 0
    stake_val = 10.0
    martingale_step = 0
    last_exit = -1000
    balance = 5000
    
    for i in range(len(candles)):
        if i < 150: continue
        
        candle = candles[i]
        price = candle["close"]
        d = dir[i]
        if dir[i] is None: continue
        
        hma_c = hma_vals[i]
        hma_p = hma[i-1] if i > 0 else hma_c
        hma_slope = hma_c - hma_p
        price_above = price > hma_c
        price_below = price < hma_c
        
        if i - last_exit < 10:
            if position and i - entry_idx >= 1:
                win = (price > entry_price) if position == "long" else (price < entry_price)
                pnl = stake * 0.80 if win else -stake
                balance += pnl
                if win: martingale_step = 0
                else: martingale_step += 1
                if martingale_step >= 3: martingale_step = 0
                stake = min(stake * 2, 50.0)
                last_exit = i
                position = None
            continue
        
        if position is None:
            stake = min(10 * (2 ** martingale_step), 50.0)
            hma_c = hma_vals[i]
            hma_p = hma[i-1] if i > 0 else hma_c
            hma_slope = hma_c - hma_p
            price_above = price > hma_c
            price_below = price < hma_c
            
            if d == 1 and price_above and hma_slope >= 0:
                position = "long"; entry_price = price; entry_idx = i
            elif d == -1 and price_below and hma_slope <= 0:
                position = "short"; entry_price = price; entry_idx = i
        
        if position and i - entry_idx >= 1:
            win = (price > entry_price) if position == "long" else (price < entry_price)
            pnl = stake * 0.80 if win else -stake
            balance += pnl
            if win: martingale_step = 0
            else: martingale_step += 1
            if martingale_step >= 3: martingale_step = 0
            stake = min(stake * 2, 50.0)
            last_exit = i
            position = None
    
    wins = sum(1 for t in trades if t['win'])
    losses = len(trades) - wins
    total_pnl = sum(t['pnl'] for t in trades)
    wr = (wins / len(trades) * 100) if trades else 0
    
    running = 0; peak = 0; max_dd = 0
    for t in trades:
        running += t['pnl']
        peak = max(peak, running)
        max_dd = max(max_dd, peak - running)
    
    freq = len(candles) / len(trades) if trades else 0
    print(f"  {symbol}: Trades={len(trades)} Freq=1/{len(candles)/len(trades):.1f} WR={wr:.1f}% PnL=${total_pnl:.2f} DD=${max_dd:.2f}")

# Run for each symbol
from bot_python.bot_1hz50v import hma, hma_direction

for symbol in ["1HZ10V", "1HZ25V", "1HZ50V", "1HZ75V"]:
    with open(f'real_{symbol}.json') as f:
        prices = json.load(f)
    
    candles = []
    for i in range(0, len(prices), 60):
        chunk = prices[i:i+60]
        if len(chunk) == 60:
            candles.append({"open": chunk[0], "high": max(chunk), "low": min(chunk), "close": chunk[-1]})
    
    # Calculate indicators
    closes = [c["close"] for c in candles]
    hma_vals = hma([c["close"] for c in candles], 30)
    hma_for_dir = hma([c["close"] for c in candles], 30)
    dir_vals = hma_direction(hma_for_dir)
    
    # Backtest
    stake = 10.0
    max_stake = 50.0
    balance = 5000
    martingale_step = 0
    last_exit = -1000
    trades = []
    position = None
    entry_price = 0
    entry_idx = 0
    stake_val = 10.0
    martingale_step = 0
    last_exit = -1000
    balance = 5000
    
    for i in range(len(candles)):
        if i < 150: continue
        
        candle = candles[i]
        price = candle["close"]
        d = dir_vals[i]
        if dir_vals[i] is None: continue
        
        hma_c = hma_vals[i]
        hma_p = hma_vals[i-1] if i > 0 else hma_c
        hma_slope = hma_c - hma_p
        price_above = price > hma_c
        price_below = price < hma_c
        
        if i - last_exit < 10:
            if position and i - entry_idx >= 1:
                win = (price > entry_price) if position == "long" else (price < entry_price)
                pnl = stake * 0.80 if win else -stake
                balance += pnl
                if win: martingale_step = 0
                else: martingale_step += 1
                if martingale_step >= 3: martingale_step = 0
                stake = min(stake * 2, 50.0)
                last_exit = i
                position = None
            continue
        
        if position is None:
            stake = min(10 * (2 ** martingale_step), 50.0)
            hma_c = hma_vals[i]
            hma_p = hma_vals[i-1] if i > 0 else hma_c
            hma_slope = hma_c - hma_p
            price_above = price > hma_c
            price_below = price < hma_c
            
            if d == 1 and price_above and hma_slope >= 0:
                position = "long"; entry_price = price; entry_idx = i
            elif d == -1 and price_below and hma_slope <= 0:
                position = "short"; entry_price = price; entry_idx = i
        
        if position and i - entry_idx >= 1:
            win = (price > entry_price) if position == "long" else (price < entry_price)
            pnl = stake * 0.80 if win else -stake
            balance += pnl
            if win: martingale_step = 0
            else: martingale_step += 1
            if martingale_step >= 3: martingale_step = 0
            stake = min(stake * 2, 50.0)
            last_exit = i
            position = None
    
    wins = sum(1 for t in trades if t['win'])
    losses = len(trades) - wins
    total_pnl = sum(t['pnl'] for t in trades)
    wr = (wins / len(trades) * 100) if trades else 0
    
    running = 0; peak = 0; max_dd = 0
    for t in trades:
        running += t['pnl']
        peak = max(peak, running)
        max_dd = max(max_dd, peak - running)
    
    freq = len(candles) / len(trades) if trades else 0
    print(f"  {symbol}: Trades={len(trades)} Freq=1/{len(candles)/len(trades):.1f} WR={wr:.1f}% PnL=${total_pnl:.2f} DD=${max_dd:.2f}")

if __name__ == "__main__":
    from bot_python.bot_1hz50v import hma, hma_direction
    
    for symbol in ["1HZ10V", "1HZ25V", "1HZ50V", "1HZ75V"]:
        with open(f'real_{symbol}.json') as f:
            prices = json.load(f)
        
        candles = []
        for i in range(0, len(prices), 60):
            chunk = prices[i:i+60]
            if len(chunk) == 60:
                candles.append({"open": chunk[0], "high": max(chunk), "low": min(chunk), "close": chunk[-1]})
        
        # Calculate indicators
        closes = [c["close"] for c in candles]
        hma_vals = hma([c["close"] for c in candles], 30)
        hma_for_dir = hma([c["close"] for c in candles], 30)
        dir_vals = hma_direction(hma_for_dir)
        
        # Backtest
        stake = 10.0
        max_stake = 50.0
        balance = 5000
        martingale_step = 0
        last_exit = -1000
        trades = []
        position = None
        entry_price = 0
        entry_idx = 0
        stake_val = 10.0
        martingale_step = 0
        last_exit = -1000
        balance = 5000
        
        for i in range(len(candles)):
            if i < 150: continue
            
            candle = candles[i]
            price = candle["close"]
            d = dir[i]
            if dir[i] is None: continue
            
            hma_c = hma_vals[i]
            hma_p = hma[i-1] if i > 0 else hma_c
            hma_slope = hma_c - hma_p
            price_above = price > hma_c
            price_below = price < hma_c
            
            if i - last_exit < 10:
                if position and i - entry_idx >= 1:
                    win = (price > entry_price) if position == "long" else (price < entry_price)
                    pnl = stake * 0.80 if win else -stake
                    balance += pnl
                    if win: martingale_step = 0
                    else: martingale_step += 1
                    if martingale_step >= 3: martingale_step = 0
                    stake = min(stake * 2, 50.0)
                    last_exit = i
                    position = None
                continue
            
            if position is None:
                stake = min(10 * (2 ** martingale_step), 50.0)
                hma_c = hma_vals[i]
                hma_p = hma[i-1] if i > 0 else hma_c
                hma_slope = hma_c - hma_p
                price_above = price > hma_c
                price_below = price < hma_c
                
                if d == 1 and price_above and hma_slope >= 0:
                    position = "long"; entry_price = price; entry_idx = i
                elif d == -1 and price_below and hma_slope <= 0:
                    position = "short"; entry_price = price; entry_idx = i
            
            if position and i - entry_idx >= 1:
                win = (price > entry_price) if position == "long" else (price < entry_price)
                pnl = stake * 0.80 if win else -stake
                balance += pnl
                if win: martingale_step = 0
                else: martingale_step += 1
                if martingale_step >= 3: martingale_step = 0
                stake = min(stake * 2, 50.0)
                last_exit = i
                position = None
        
        wins = sum(1 for t in trades if t['win'])
        losses = len(trades) - wins
        total_pnl = sum(t['pnl'] for t in trades)
        wr = (wins / len(trades) * 100) if trades else 0
        
        running = 0; peak = 0; max_dd = 0
        for t in trades:
            running += t['pnl']
            peak = max(peak, running)
            max_dd = max(max_dd, peak - running)
        
        freq = len(candles) / len(trades) if trades else 0
        print(f"  {symbol}: Trades={len(trades)} Freq=1/{len(candles)/len(trades):.1f} WR={wr:.1f}% PnL=${total_pnl:.2f} DD=${max_dd:.2f}")

if __name__ == "__main__":
    from bot_python.bot_1hz50v import hma, hma_direction
    
    for symbol in ["1HZ10V", "1HZ25V", "1HZ50V", "1HZ75V"]:
        with open(f'real_{symbol}.json') as f:
            prices = json.load(f)
        
        candles = []
        for i in range(0, len(prices), 60):
            chunk = prices[i:i+60]
            if len(chunk) == 60:
                candles.append({"open": chunk[0], "high": max(chunk), "low": min(chunk), "close": chunk[-1]})
        
        # Calculate indicators
        closes = [c["close"] for c in candles]
        hma_vals = hma([c["close"] for c in candles], 30)
        hma_for_dir = hma([c["close"] for c in candles], 30)
        dir_vals = hma_direction(hma_for_dir)
        
        # Backtest
        stake = 10.0
        max_stake = 50.0
        balance = 5000
        martingale_step = 0
        last_exit = -1000
        trades = []
        position = None
        entry_price = 0
        entry_idx = 0
        stake_val = 10.0
        martingale_step = 0
        last_exit = -1000
        balance = 5000
        
        for i in range(len(candles)):
            if i < 150: continue
            
            candle = candles[i]
            price = candle["close"]
            d = dir[i]
            if dir[i] is None: continue
            
            hma_c = hma_vals[i]
            hma_p = hma[i-1] if i > 0 else hma_c
            hma_slope = hma_c - hma_p
            price_above = price > hma_c
            price_below = price < hma_c
            
            if i - last_exit < 10:
                if position and i - entry_idx >= 1:
                    win = (price > entry_price) if position == "long" else (price < entry_price)
                    pnl = stake * 0.80 if win else -stake
                    balance += pnl
                    if win: martingale_step = 0
                    else: martingale_step += 1
                    if martingale_step >= 3: martingale_step = 0
                    stake = min(stake * 2, 50.0)
                    last_exit = i
                    position = None
                continue
            
            if position is None:
                stake = min(10 * (2 ** martingale_step), 50.0)
                hma_c = hma_vals[i]
                hma_p = hma[i-1] if i > 0 else hma_c
                hma_slope = hma_c - hma_p
                price_above = price > hma_c
                price_below = price < hma_c
                
                if d == 1 and price_above and hma_slope >= 0:
                    position = "long"; entry_price = price; entry_idx = i
                elif d == -1 and price_below and hma_slope <= 0:
                    position = "short"; entry_price = price; entry_idx = i
            
            if position and i - entry_idx >= 1:
                win = (price > entry_price) if position == "long" else (price < entry_price)
                pnl = stake * 0.80 if win else -stake
                balance += pnl
                if win: martingale_step = 0
                else: martingale_step += 1
                if martingale_step >= 3: martingale_step = 0
                stake = min(stake * 2, 50.0)
                last_exit = i
                position = None
        
        wins = sum(1 for t in trades if t['win'])
        losses = len(trades) - wins
        total_pnl = sum(t['pnl'] for t in trades)
        wr = (wins / len(trades) * 100) if trades else 0
        
        running = 0; peak = 0; max_dd = 0
        for t in trades:
            running += t['pnl']
            peak = max(peak, running)
            max_dd = max(max_dd, peak - running)
        
        freq = len(candles) / len(trades) if trades else 0
        print(f"  {symbol}: Trades={len(trades)} Freq=1/{len(candles)/len(trades):.1f} WR={wr:.1f}% PnL=${total_pnl:.2f} DD=${max_dd:.2f}")